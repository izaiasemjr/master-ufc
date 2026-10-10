// Batch FPFH matching for configuration-defined recognition experiments.
//
// Descriptor files are loaded once, then all probe x gallery pairs are
// evaluated in memory.  Per-pair time deliberately starts only at the
// correspondence calculation: disk I/O, process start-up and index building
// are reported separately and never included in time_match_ms.

// PCL ships explicit instantiations for its default L2 tree only.  The paper
// mode needs an L1 FLANN distance, so enable the template implementation for
// this translation unit before including the k-d tree headers.
#define PCL_NO_PRECOMPILE

#include <pcl/io/pcd_io.h>
#include <pcl/kdtree/kdtree_flann.h>
#include <pcl/point_types.h>
#include <flann/algorithms/dist.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {

using Feature = pcl::FPFHSignature33;
using FeatureCloud = pcl::PointCloud<Feature>;
using L1Tree = pcl::KdTreeFLANN<Feature, flann::L1<float>>;

struct Item {
  std::string role;
  std::string subject;
  std::string type;
  std::string expression;
  std::string sample;
  std::string path;
  FeatureCloud::Ptr features{new FeatureCloud};
  std::unique_ptr<L1Tree> tree;

  std::string id() const {
    return subject + "_" + type + "_" + expression + "_" + sample;
  }
};

struct Arguments {
  std::string input;
  std::string output;
  std::string timing_output;
  std::string correspondence;
  std::vector<std::size_t> k_values;
};

double milliseconds_since(const std::chrono::steady_clock::time_point& start) {
  return std::chrono::duration<double, std::milli>(
      std::chrono::steady_clock::now() - start).count();
}

std::vector<std::string> split(const std::string& value, char separator) {
  std::vector<std::string> parts;
  std::string part;
  std::istringstream input(value);
  while (std::getline(input, part, separator)) parts.push_back(part);
  return parts;
}

std::string require_value(int& index, int argc, char** argv, const char* option) {
  if (++index >= argc) throw std::runtime_error(std::string("Missing value for ") + option);
  return argv[index];
}

Arguments parse_arguments(int argc, char** argv) {
  Arguments args;
  for (int index = 1; index < argc; ++index) {
    const std::string option(argv[index]);
    if (option == "--input") args.input = require_value(index, argc, argv, "--input");
    else if (option == "--output") args.output = require_value(index, argc, argv, "--output");
    else if (option == "--timing-output") args.timing_output = require_value(index, argc, argv, "--timing-output");
    else if (option == "--correspondence") args.correspondence = require_value(index, argc, argv, "--correspondence");
    else if (option == "--ks") {
      for (const auto& raw : split(require_value(index, argc, argv, "--ks"), ',')) {
        try {
          const auto parsed = std::stoull(raw);
          if (parsed == 0) throw std::runtime_error("K must be positive");
          args.k_values.push_back(static_cast<std::size_t>(parsed));
        } catch (const std::exception&) {
          throw std::runtime_error("Invalid K value: " + raw);
        }
      }
    } else if (option == "--help") {
      std::cout << "Usage: matching_batch --input manifest.tsv --output scores.csv "
                << "--timing-output timing.csv --correspondence fixed|dynamic --ks 2,5,10\n";
      std::exit(0);
    } else {
      throw std::runtime_error("Unknown option: " + option);
    }
  }
  if (args.input.empty() || args.output.empty() || args.timing_output.empty() ||
      args.correspondence.empty() || args.k_values.empty()) {
    throw std::runtime_error("--input, --output, --timing-output, --correspondence and --ks are required");
  }
  if (args.correspondence != "fixed" && args.correspondence != "dynamic") {
    throw std::runtime_error("--correspondence must be fixed or dynamic");
  }
  std::sort(args.k_values.begin(), args.k_values.end());
  args.k_values.erase(std::unique(args.k_values.begin(), args.k_values.end()), args.k_values.end());
  return args;
}

void validate_features(const Item& item) {
  if (item.features->empty()) throw std::runtime_error("Descriptor has no points: " + item.path);
  for (std::size_t point = 0; point < item.features->size(); ++point) {
    for (float bin : item.features->points[point].histogram) {
      if (!std::isfinite(bin)) {
        throw std::runtime_error("Descriptor has non-finite FPFH value: " + item.path +
                                 " (point " + std::to_string(point) + ")");
      }
    }
  }
}

std::vector<Item> load_manifest(const std::string& manifest) {
  std::ifstream input(manifest);
  if (!input) throw std::runtime_error("Cannot open descriptor manifest: " + manifest);
  std::vector<Item> items;
  std::unordered_set<std::string> ids;
  std::string line;
  std::size_t line_number = 0;
  while (std::getline(input, line)) {
    ++line_number;
    if (line.empty() || line[0] == '#') continue;
    const auto fields = split(line, '\t');
    if (fields.size() != 6) {
      throw std::runtime_error("Expected six tab-separated fields in manifest line " +
                               std::to_string(line_number));
    }
    Item item{fields[0], fields[1], fields[2], fields[3], fields[4], fields[5]};
    if (item.role != "gallery" && item.role != "probe") {
      throw std::runtime_error("Invalid role in manifest line " + std::to_string(line_number));
    }
    const std::string unique_id = item.role + ":" + item.id();
    if (!ids.insert(unique_id).second) {
      throw std::runtime_error("Duplicate descriptor identity in manifest: " + unique_id);
    }
    if (pcl::io::loadPCDFile<Feature>(item.path, *item.features) != 0) {
      throw std::runtime_error("Cannot load descriptor PCD: " + item.path);
    }
    validate_features(item);
    items.push_back(std::move(item));
  }
  if (items.empty()) throw std::runtime_error("Descriptor manifest is empty: " + manifest);
  return items;
}

float l1_distance(const Feature& first, const Feature& second) {
  float distance = 0.0F;
  for (std::size_t bin = 0; bin < 33; ++bin) {
    distance += std::fabs(first.histogram[bin] - second.histogram[bin]);
  }
  return distance;
}

std::vector<float> fixed_scores(const Item& probe, const Item& gallery) {
  if (probe.features->size() != gallery.features->size()) {
    throw std::runtime_error("Fixed correspondence requires equal descriptor counts for " +
                             probe.id() + " (" + std::to_string(probe.features->size()) + ") and " +
                             gallery.id() + " (" + std::to_string(gallery.features->size()) + ")");
  }
  std::vector<float> scores;
  scores.reserve(probe.features->size());
  for (std::size_t index = 0; index < probe.features->size(); ++index) {
    scores.push_back(l1_distance(probe.features->points[index], gallery.features->points[index]));
  }
  return scores;
}

std::vector<float> dynamic_scores(const Item& probe, const Item& gallery) {
  // The smaller descriptor set queries the L1 KD-tree for the larger set, as
  // in the historical dynamic-correspondence method.
  const Item* query = &probe;
  const Item* target = &gallery;
  if (probe.features->size() > gallery.features->size()) {
    query = &gallery;
    target = &probe;
  }
  if (!target->tree) throw std::runtime_error("Internal error: L1 index is unavailable for " + target->id());
  std::vector<float> scores;
  scores.reserve(query->features->size());
  std::vector<int> indices(1);
  std::vector<float> ignored_distances(1);
  for (const auto& feature : query->features->points) {
    if (target->tree->nearestKSearch(feature, 1, indices, ignored_distances) != 1) {
      throw std::runtime_error("L1 nearest-neighbour search failed for " + probe.id() + " x " + gallery.id());
    }
    scores.push_back(l1_distance(feature, target->features->points[indices[0]]));
  }
  return scores;
}

void write_timing(const std::string& path, double loading_ms, double index_ms,
                  double pair_ms, std::size_t pair_count) {
  const std::string temporary = path + ".tmp";
  std::ofstream output(temporary);
  if (!output) throw std::runtime_error("Cannot write timing output: " + temporary);
  output << "metric,value\n" << std::fixed << std::setprecision(6)
         << "descriptor_loading_ms," << loading_ms << "\n"
         << "index_build_ms," << index_ms << "\n"
         << "pair_matching_ms," << pair_ms << "\n"
         << "pair_count," << pair_count << "\n";
  output.close();
  if (std::rename(temporary.c_str(), path.c_str()) != 0) {
    throw std::runtime_error("Cannot finalize timing output: " + path);
  }
}

void match_all(const Arguments& args) {
  const auto loading_start = std::chrono::steady_clock::now();
  auto items = load_manifest(args.input);
  const double loading_ms = milliseconds_since(loading_start);

  std::vector<Item*> probes;
  std::vector<Item*> galleries;
  for (auto& item : items) (item.role == "probe" ? probes : galleries).push_back(&item);
  if (probes.empty() || galleries.empty()) throw std::runtime_error("Manifest needs at least one probe and one gallery descriptor");

  double index_ms = 0.0;
  if (args.correspondence == "dynamic") {
    const auto index_start = std::chrono::steady_clock::now();
    for (auto& item : items) {
      item.tree.reset(new L1Tree);
      item.tree->setInputCloud(item.features);
    }
    index_ms = milliseconds_since(index_start);
  }

  const std::string temporary = args.output + ".tmp";
  std::ofstream output(temporary);
  if (!output) throw std::runtime_error("Cannot write matching output: " + temporary);
  output << "k,probe_subject,probe_type,probe_expression,probe_sample,"
         << "gallery_subject,gallery_type,gallery_expression,gallery_sample,"
         << "distance_mean_l1,correspondence_count,selected_count,time_match_ms\n";
  output << std::fixed << std::setprecision(9);

  double all_pairs_ms = 0.0;
  std::size_t pair_count = 0;
  for (const Item* probe : probes) {
    for (const Item* gallery : galleries) {
      // The measured scope begins here. It is only correspondence search,
      // L1 score calculation, sorting, and the configured K reductions.
      const auto pair_start = std::chrono::steady_clock::now();
      auto scores = args.correspondence == "fixed" ? fixed_scores(*probe, *gallery)
                                                     : dynamic_scores(*probe, *gallery);
      std::sort(scores.begin(), scores.end());
      std::vector<double> prefix(scores.size() + 1, 0.0);
      for (std::size_t index = 0; index < scores.size(); ++index) prefix[index + 1] = prefix[index] + scores[index];
      const double pair_ms = milliseconds_since(pair_start);
      all_pairs_ms += pair_ms;
      ++pair_count;
      for (const auto requested_k : args.k_values) {
        const std::size_t selected = std::min(requested_k, scores.size());
        const double mean = prefix[selected] / static_cast<double>(selected);
        output << requested_k << ',' << probe->subject << ',' << probe->type << ','
               << probe->expression << ',' << probe->sample << ',' << gallery->subject << ','
               << gallery->type << ',' << gallery->expression << ',' << gallery->sample << ','
               << mean << ',' << scores.size() << ',' << selected << ',' << pair_ms << '\n';
      }
    }
  }
  output.close();
  if (!output) throw std::runtime_error("Failed while writing matching output: " + temporary);
  if (std::rename(temporary.c_str(), args.output.c_str()) != 0) {
    throw std::runtime_error("Cannot finalize matching output: " + args.output);
  }
  write_timing(args.timing_output, loading_ms, index_ms, all_pairs_ms, pair_count);
}

}  // namespace

int main(int argc, char** argv) {
  try {
    match_all(parse_arguments(argc, argv));
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "matching_batch: " << error.what() << std::endl;
    return 1;
  }
}
