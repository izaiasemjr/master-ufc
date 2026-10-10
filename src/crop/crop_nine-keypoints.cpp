#include "./include/functions.hpp"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace
{

    struct KeypointCrop
    {
        const char *name;
        // The numbering in keypoints-rays.conf is one-based.  PCL point-cloud
        // indices are zero-based, so this value is converted before access.
        std::size_t landmark_number;
        float radius;
    };

    const std::array<KeypointCrop, 9> kKeypointCrops = {{
        {"nose_tip", 14U, 25.0F},
        {"mouth_cd", 21U, 45.0F},
        {"mouth_cu", 17U, 35.0F},
        {"mouth_l", 16U, 45.0F},
        {"mouth_r", 18U, 45.0F},
        {"eye_li", 8U, 45.0F},
        {"eye_le", 7U, 45.0F},
        {"eye_ri", 9U, 45.0F},
        {"eye_re", 10U, 45.0F},
        // -- -- -- -- -- -- -- -- -- -- -- -- -
        // {"nose_tip", 14U, 10.0F},
        // {"mouth_cd", 21U, 20.0F},
        // {"mouth_cu", 17U, 15.0F},
        // {"mouth_l", 16U, 20.0F},
        // {"mouth_r", 18U, 20.0F},
        // {"eye_li", 8U, 15.0F},
        // {"eye_le", 7U, 15.0F},
        // {"eye_ri", 9U, 20.0F},
        // {"eye_re", 10U, 20.0F},

    }};

    bool hasFiniteCoordinates(const pcl::PointXYZ &point)
    {
        return std::isfinite(point.x) && std::isfinite(point.y) &&
               std::isfinite(point.z);
    }

    bool hasValue(const std::vector<std::string> &values)
    {
        return !values.empty() && !values.front().empty();
    }

    void printUsage(const char *executable)
    {
        std::cerr << "Usage: " << executable
                  << " -cloud <face.pcd> -keypoints <landmarks.pcd>"
                  << " -output <crop.pcd> [-offset x,y,z]\n";
    }

    bool readOptionalOffset(int argc, char **argv, pcl::PointXYZ &offset)
    {
        std::string offset_argument;
        if (pcl::console::parse_argument(argc, argv, "-offset", offset_argument) <=
            0)
        {
            offset.x = 0.0F;
            offset.y = 0.0F;
            offset.z = 0.0F;
            return true;
        }

        std::stringstream stream(offset_argument);
        std::string coordinate;
        float *const coordinates[] = {&offset.x, &offset.y, &offset.z};
        for (float *const destination : coordinates)
        {
            if (!std::getline(stream, coordinate, ','))
            {
                return false;
            }

            try
            {
                *destination = std::stof(coordinate);
            }
            catch (const std::exception &)
            {
                return false;
            }
        }

        if (std::getline(stream, coordinate, ','))
        {
            return false;
        }
        return hasFiniteCoordinates(offset);
    }

} // namespace

int main(int argc, char **argv)
{
    // The command-line names are kept compatible with crop.cpp.  The radius
    // is intentionally not an argument: each region uses its fixed radius
    // from keypoints-rays.conf.
    const std::vector<std::string> cloud_paths =
        get_parameters(argc, argv, "-cloud", ",");
    const std::vector<std::string> landmark_paths =
        get_parameters(argc, argv, "-keypoints", ",");
    const std::vector<std::string> output_paths =
        get_parameters(argc, argv, "-output", ",");

    if (!hasValue(cloud_paths) || !hasValue(landmark_paths) ||
        !hasValue(output_paths))
    {
        printUsage(argv[0]);
        return 1;
    }

    pcl::PointXYZ offset;
    if (!readOptionalOffset(argc, argv, offset))
    {
        std::cerr << "Invalid -offset; expected three finite values: x,y,z.\n";
        printUsage(argv[0]);
        return 1;
    }

    pcl::PointCloud<pcl::PointXYZ>::Ptr cloud(
        new pcl::PointCloud<pcl::PointXYZ>);
    openCloudPCD(cloud_paths.front(), cloud);

    pcl::PointCloud<pcl::PointXYZ>::Ptr landmarks(
        new pcl::PointCloud<pcl::PointXYZ>);
    openCloudPCD(landmark_paths.front(), landmarks);

    // KdTreeFLANN requires finite source coordinates. Keep the map to the
    // original cloud so the output can retain its original point order.
    pcl::PointCloud<pcl::PointXYZ>::Ptr finite_cloud(
        new pcl::PointCloud<pcl::PointXYZ>);
    std::vector<std::size_t> finite_to_source_index;
    finite_cloud->points.reserve(cloud->points.size());
    finite_to_source_index.reserve(cloud->points.size());
    for (std::size_t i = 0; i < cloud->points.size(); ++i)
    {
        if (hasFiniteCoordinates(cloud->points[i]))
        {
            finite_cloud->points.push_back(cloud->points[i]);
            finite_to_source_index.push_back(i);
        }
    }
    finite_cloud->width =
        static_cast<std::uint32_t>(finite_cloud->points.size());
    finite_cloud->height = 1U;
    finite_cloud->is_dense = true;

    // Each source point is marked at most once so that intersecting spheres
    // produce a union of crops rather than duplicated points in the output.
    std::vector<bool> selected(cloud->points.size(), false);
    pcl::KdTreeFLANN<pcl::PointXYZ> kdtree;
    if (!finite_cloud->points.empty())
    {
        kdtree.setInputCloud(finite_cloud);
    }

    std::size_t valid_keypoints = 0;
    for (const KeypointCrop &keypoint_crop : kKeypointCrops)
    {
        const std::size_t point_index = keypoint_crop.landmark_number - 1U;
        if (point_index >= landmarks->points.size())
        {
            std::cerr << "Skipping " << keypoint_crop.name
                      << ": landmark " << keypoint_crop.landmark_number
                      << " is not present in the keypoint cloud.\n";
            continue;
        }

        const pcl::PointXYZ &keypoint = landmarks->points[point_index];
        if (!hasFiniteCoordinates(keypoint))
        {
            std::cerr << "Skipping " << keypoint_crop.name
                      << ": landmark " << keypoint_crop.landmark_number
                      << " has invalid x, y or z coordinates.\n";
            continue;
        }

        pcl::PointXYZ crop_center = keypoint;
        crop_center.x += offset.x;
        crop_center.y += offset.y;
        crop_center.z += offset.z;
        if (!hasFiniteCoordinates(crop_center))
        {
            std::cerr << "Skipping " << keypoint_crop.name
                      << ": offset produced invalid x, y or z coordinates.\n";
            continue;
        }

        ++valid_keypoints;
        std::vector<int> point_indices;
        std::vector<float> squared_distances;
        if (!finite_cloud->points.empty())
        {
            kdtree.radiusSearch(crop_center, keypoint_crop.radius,
                                point_indices, squared_distances);
        }

        for (const int finite_index : point_indices)
        {
            if (finite_index < 0)
            {
                continue;
            }

            const std::size_t finite_index_as_size =
                static_cast<std::size_t>(finite_index);
            if (finite_index_as_size < finite_to_source_index.size())
            {
                selected[finite_to_source_index[finite_index_as_size]] = true;
            }
        }
    }

    pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_crop(
        new pcl::PointCloud<pcl::PointXYZ>);
    cloud_crop->header = cloud->header;
    cloud_crop->sensor_origin_ = cloud->sensor_origin_;
    cloud_crop->sensor_orientation_ = cloud->sensor_orientation_;
    cloud_crop->is_dense = true;

    for (std::size_t i = 0; i < selected.size(); ++i)
    {
        if (selected[i])
        {
            cloud_crop->points.push_back(cloud->points[i]);
        }
    }
    cloud_crop->width = static_cast<std::uint32_t>(cloud_crop->points.size());
    cloud_crop->height = 1U;

    if (pcl::io::savePCDFileASCII(output_paths.front(), *cloud_crop) != 0)
    {
        std::cerr << "Couldn't write cropped cloud: " << output_paths.front()
                  << "\n";
        return 1;
    }

    std::cout << "Cropped with " << valid_keypoints << "/"
              << kKeypointCrops.size() << " valid keypoints; wrote "
              << cloud_crop->points.size() << " unique points.\n";
    return 0;
}
