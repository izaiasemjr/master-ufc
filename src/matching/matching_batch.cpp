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
#include <limits>
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
  std::string pair_distances_output;
  std::string correspondence;
  std::string aggregation = "mean";
  std::vector<std::size_t> k_values;
  std::vector<double> dp_values;
  bool incremental = false;
  std::size_t corr_min = 1;
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
    else if (option == "--pair-distances-output") args.pair_distances_output = require_value(index, argc, argv, "--pair-distances-output");
    else if (option == "--correspondence") args.correspondence = require_value(index, argc, argv, "--correspondence");
    else if (option == "--aggregation") args.aggregation = require_value(index, argc, argv, "--aggregation");
    else if (option == "--corr-min") {
      const auto raw = require_value(index, argc, argv, "--corr-min");
      if (raw.empty() || raw.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error("--corr-min must be a positive integer");
      const auto value = std::stoull(raw);
      if (value == 0 || value > std::numeric_limits<std::size_t>::max())
        throw std::runtime_error("--corr-min must be a positive integer");
      args.corr_min = static_cast<std::size_t>(value);
    }
    else if (option == "--dps" || option == "--dp-thresholds") {
      if (!args.dp_values.empty()) throw std::runtime_error("Choose only one adaptive selection option");
      args.incremental = option == "--dp-thresholds";
      for (const auto& raw : split(require_value(index, argc, argv, option.c_str()), ',')) {
        std::size_t consumed = 0;
        const double value = std::stod(raw, &consumed);
        if (consumed != raw.size() || !std::isfinite(value) || value <= 0)
          throw std::runtime_error("DP must be finite and positive: " + raw);
        args.dp_values.push_back(value);
      }
    } else if (option == "--ks") {
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
                << "--timing-output timing.csv [--pair-distances-output distances.csv] "
                << "--correspondence fixed|dynamic [--aggregation mean|median] [--corr-min 5 (with --dps)] (--ks 2,5,10 | --dps 1,2,5 | --dp-thresholds 1.1,1.5,2)\n";
      std::exit(0);
    } else {
      throw std::runtime_error("Unknown option: " + option);
    }
  }
  if (args.input.empty() || args.output.empty() || args.timing_output.empty() ||
      args.correspondence.empty() || (args.k_values.empty() == args.dp_values.empty())) {
    throw std::runtime_error("--input, --output, --timing-output, --correspondence and exactly one of --ks, --dps or --dp-thresholds are required");
  }
  if (args.corr_min != 1 && (args.dp_values.empty() || args.incremental))
    throw std::runtime_error("--corr-min is supported only with absolute-DP selection (--dps)");
  if (args.correspondence != "fixed" && args.correspondence != "dynamic") {
    throw std::runtime_error("--correspondence must be fixed or dynamic");
  }
  if (args.aggregation != "mean" && args.aggregation != "median") {
    throw std::runtime_error("--aggregation must be mean or median");
  }
  std::sort(args.k_values.begin(), args.k_values.end());
  args.k_values.erase(std::unique(args.k_values.begin(), args.k_values.end()), args.k_values.end());
  std::sort(args.dp_values.begin(), args.dp_values.end());
  args.dp_values.erase(std::unique(args.dp_values.begin(), args.dp_values.end()), args.dp_values.end());
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
  output << (args.dp_values.empty() ? "k," : (args.incremental ? "dp_threshold," : "dp,")) << "probe_subject,probe_type,probe_expression,probe_sample,"
         << "gallery_subject,gallery_type,gallery_expression,gallery_sample,"
         << "distance_" << args.aggregation << "_l1,correspondence_count,selected_count,time_match_ms"
         << (args.dp_values.empty() ? "\n" : (args.incremental ? ",selected_stddev,next_stddev,next_stddev_ratio\n" : ",selected_stddev,corr_min\n"));
  if (args.dp_values.empty()) output << std::fixed << std::setprecision(9);
  else output << std::setprecision(17);

  std::ofstream pair_distances;
  std::string distances_temporary;
  if (!args.pair_distances_output.empty()) {
    distances_temporary = args.pair_distances_output + ".tmp";
    pair_distances.open(distances_temporary);
    if (!pair_distances) throw std::runtime_error("Cannot write pair-distance output: " + distances_temporary);
    pair_distances << "probe_subject,probe_type,probe_expression,probe_sample,"
                   << "gallery_subject,gallery_type,gallery_expression,gallery_sample,"
                   << "pair_index,distance_l1\n";
    pair_distances << std::fixed << std::setprecision(9);
  }

  double all_pairs_ms = 0.0;
  std::size_t pair_count = 0;
  for (const Item* probe : probes) {
    for (const Item* gallery : galleries) {
      // The measured scope begins here. It is only correspondence search,
      // L1 score calculation, sorting, and the configured K reductions.
      const auto pair_start = std::chrono::steady_clock::now();
      auto scores = args.correspondence == "fixed" ? fixed_scores(*probe, *gallery)
                                                     : dynamic_scores(*probe, *gallery);
      if (!args.dp_values.empty() && !args.incremental && scores.size() < args.corr_min)
        throw std::runtime_error("Not enough correspondences for corr_min=" + std::to_string(args.corr_min) +
                                 ": " + probe->id() + " x " + gallery->id());
      std::sort(scores.begin(), scores.end());
      if (pair_distances) {
        for (std::size_t index = 0; index < scores.size(); ++index) {
          pair_distances << probe->subject << ',' << probe->type << ',' << probe->expression << ','
                         << probe->sample << ',' << gallery->subject << ',' << gallery->type << ','
                         << gallery->expression << ',' << gallery->sample << ',' << index + 1 << ','
                         << scores[index] << '\n';
        }
      }
      std::vector<double> prefix(scores.size() + 1, 0.0);
      for (std::size_t index = 0; index < scores.size(); ++index) prefix[index + 1] = prefix[index] + scores[index];
      // Welford population moments for each sorted prefix, shared by
      // absolute-DP selection and incremental stddev-ratio selection.
      std::vector<double> stddev(scores.size() + 1, 0.0);
      if (!args.dp_values.empty()) {
        double mean = 0.0, m2 = 0.0;
        for (std::size_t n = 1; n <= scores.size(); ++n) {
          const double delta = scores[n - 1] - mean;
          mean += delta / n;
          m2 += delta * (scores[n - 1] - mean);
          stddev[n] = std::sqrt(std::max(0.0, m2 / n));
        }
      }
      std::vector<std::size_t> selections;
      for (const auto k : args.k_values) selections.push_back(std::min(k, scores.size()));
      for (const auto dp : args.dp_values) {
        std::size_t selected = 1;
        if (args.incremental) {
          selected = std::min<std::size_t>(2, scores.size());
          while (selected < scores.size()) {
            const double current = stddev[selected], next = stddev[selected + 1];
            const double ratio = current > 0 ? next / current
                : (next > 0 ? std::numeric_limits<double>::infinity() : 1.0);
            if (ratio > dp) break;  // Reject next; keep the current prefix.
            ++selected;
          }
        } else {
          // Keep at least corr_min even if its stddev violates DP. Inspect
          // all longer prefixes because sorted-prefix stddev is not monotonic.
          selected = args.corr_min;
          for (std::size_t n = args.corr_min + 1; n <= scores.size(); ++n)
            if (stddev[n] < dp) selected = n;
        }
        selections.push_back(selected);
      }
      const double pair_ms = milliseconds_since(pair_start);
      all_pairs_ms += pair_ms;
      ++pair_count;
      for (std::size_t index = 0; index < selections.size(); ++index) {
        const std::size_t selected = selections[index];
        const double score = args.aggregation == "median"
            ? (static_cast<double>(scores[(selected - 1) / 2]) + scores[selected / 2]) / 2.0
            : prefix[selected] / static_cast<double>(selected);
        if (args.dp_values.empty()) output << args.k_values[index];
        else output << args.dp_values[index];
        output << ',' << probe->subject << ',' << probe->type << ','
               << probe->expression << ',' << probe->sample << ',' << gallery->subject << ','
               << gallery->type << ',' << gallery->expression << ',' << gallery->sample << ','
               << score << ',' << scores.size() << ',' << selected << ',' << pair_ms;
        if (!args.dp_values.empty()) output << ',' << stddev[selected];
        if (!args.dp_values.empty() && !args.incremental) output << ',' << args.corr_min;
        if (args.incremental) {
          output << ',';
          if (selected < scores.size()) {
            const double current = stddev[selected], next = stddev[selected + 1];
            const double ratio = current > 0 ? next / current
                : (next > 0 ? std::numeric_limits<double>::infinity() : 1.0);
            output << next << ',' << ratio;
          } else output << ',';  // No next prefix when all pairs were selected.
        }
        output << '\n';
      }
    }
  }
  output.close();
  if (!output) throw std::runtime_error("Failed while writing matching output: " + temporary);
  if (std::rename(temporary.c_str(), args.output.c_str()) != 0) {
    throw std::runtime_error("Cannot finalize matching output: " + args.output);
  }
  if (pair_distances) {
    pair_distances.close();
    if (!pair_distances) throw std::runtime_error("Failed while writing pair-distance output: " + distances_temporary);
    if (std::rename(distances_temporary.c_str(), args.pair_distances_output.c_str()) != 0) {
      throw std::runtime_error("Cannot finalize pair-distance output: " + args.pair_distances_output);
    }
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
