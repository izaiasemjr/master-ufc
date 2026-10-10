// Extract FPFH descriptors at keypoints supplied in a PCD file.
//
// Methodology preserved from the dissertation implementation:
//   1. estimate surface normals over the cropped face;
//   2. use the supplied keypoints as FPFH query points;
//   3. compute FPFH against the complete cropped face as search surface.

#include <cmath>
#include <iostream>
#include <string>
#include <vector>

#include <pcl/console/parse.h>
#include <pcl/features/fpfh.h>
#include <pcl/features/normal_3d_omp.h>
#include <pcl/io/pcd_io.h>
#include <pcl/search/kdtree.h>

namespace {

bool argument(int argc, char** argv, const char* name, std::string& value) {
  if (pcl::console::parse_argument(argc, argv, name, value) <= 0) {
    std::cerr << "Missing required argument " << name << std::endl;
    return false;
  }
  return true;
}

bool parse_prefixed_path(const std::string& value, const std::string& prefix,
                         std::string& path) {
  if (value.rfind(prefix, 0) != 0 || value.size() == prefix.size()) {
    std::cerr << "Expected " << prefix << "<path>, received: " << value << std::endl;
    return false;
  }
  path = value.substr(prefix.size());
  return true;
}

bool parse_fpfh_radius(const std::string& value, float& radius) {
  constexpr const char* prefix = "fpfh,";
  if (value.rfind(prefix, 0) != 0) {
    std::cerr << "Only FPFH is supported; expected fpfh,<radius>, received: " << value << std::endl;
    return false;
  }
  try {
    radius = std::stof(value.substr(std::char_traits<char>::length(prefix)));
  } catch (const std::exception&) {
    std::cerr << "Invalid FPFH radius: " << value << std::endl;
    return false;
  }
  if (!(radius > 0.0F)) {
    std::cerr << "FPFH radius must be positive." << std::endl;
    return false;
  }
  return true;
}

bool valid_descriptors(const pcl::PointCloud<pcl::FPFHSignature33>& descriptors) {
  for (const auto& descriptor : descriptors.points) {
    for (float value : descriptor.histogram) {
      if (!std::isfinite(value)) {
        return false;
      }
    }
  }
  return true;
}

}  // namespace

int main(int argc, char** argv) {
  std::string cloud_path, normal_radius_text, keypoint_option, feature_option, output_path;
  if (!argument(argc, argv, "-cloud", cloud_path) ||
      !argument(argc, argv, "-normal", normal_radius_text) ||
      !argument(argc, argv, "-keypoints", keypoint_option) ||
      !argument(argc, argv, "-features", feature_option) ||
      !argument(argc, argv, "-output", output_path)) {
    return 2;
  }

  std::string keypoint_path;
  if (!parse_prefixed_path(keypoint_option, "from_file,", keypoint_path)) {
    return 2;
  }

  float normal_radius = 0.0F;
  try {
    normal_radius = std::stof(normal_radius_text);
  } catch (const std::exception&) {
    std::cerr << "Invalid normal radius: " << normal_radius_text << std::endl;
    return 2;
  }
  if (!(normal_radius > 0.0F)) {
    std::cerr << "Normal radius must be positive." << std::endl;
    return 2;
  }

  float feature_radius = 0.0F;
  if (!parse_fpfh_radius(feature_option, feature_radius)) {
    return 2;
  }

  pcl::PointCloud<pcl::PointXYZ>::Ptr cloud(new pcl::PointCloud<pcl::PointXYZ>);
  pcl::PointCloud<pcl::PointXYZ>::Ptr keypoints(new pcl::PointCloud<pcl::PointXYZ>);
  if (pcl::io::loadPCDFile(cloud_path, *cloud) < 0) {
    std::cerr << "Unable to read cloud: " << cloud_path << std::endl;
    return 3;
  }
  if (pcl::io::loadPCDFile(keypoint_path, *keypoints) < 0) {
    std::cerr << "Unable to read keypoints: " << keypoint_path << std::endl;
    return 3;
  }
  if (cloud->empty() || keypoints->empty()) {
    std::cerr << "Cloud and keypoint files must both contain points." << std::endl;
    return 3;
  }

  pcl::PointCloud<pcl::Normal>::Ptr normals(new pcl::PointCloud<pcl::Normal>);
  pcl::NormalEstimationOMP<pcl::PointXYZ, pcl::Normal> normal_estimation;
  normal_estimation.setInputCloud(cloud);
  normal_estimation.setSearchMethod(
      pcl::search::KdTree<pcl::PointXYZ>::Ptr(new pcl::search::KdTree<pcl::PointXYZ>));
  normal_estimation.setRadiusSearch(normal_radius);
  normal_estimation.compute(*normals);

  pcl::PointCloud<pcl::FPFHSignature33> descriptors;
  pcl::FPFHEstimation<pcl::PointXYZ, pcl::Normal, pcl::FPFHSignature33> fpfh;
  fpfh.setInputCloud(keypoints);
  fpfh.setSearchSurface(cloud);
  fpfh.setInputNormals(normals);
  fpfh.setSearchMethod(
      pcl::search::KdTree<pcl::PointXYZ>::Ptr(new pcl::search::KdTree<pcl::PointXYZ>));
  fpfh.setRadiusSearch(feature_radius);
  fpfh.compute(descriptors);

  if (descriptors.size() != keypoints->size() || !valid_descriptors(descriptors)) {
    std::cerr << "FPFH extraction generated invalid or incomplete descriptors: "
              << descriptors.size() << " for " << keypoints->size() << " keypoints." << std::endl;
    return 4;
  }
  if (pcl::io::savePCDFileASCII(output_path, descriptors) < 0) {
    std::cerr << "Unable to save descriptors: " << output_path << std::endl;
    return 5;
  }
  std::cout << "Extracted " << descriptors.size() << " FPFH descriptors." << std::endl;
  return 0;
}
