/*
 * by
 * Izaias Junior
 * Interfaces Group - UFC
 */


#include "../include/functions.hpp"
#include <boost/algorithm/string.hpp>


using namespace std;


vector<string> get_parameters(int argc, char **argv ,const char *symbol, const char *delimiter ){

    std::string params_string;
    bool refine_alignment = pcl::console::parse_argument (argc, argv, symbol, params_string) > 0;
    if (!refine_alignment){PCL_ERROR ("Couldn't read %s parameters \n", symbol); exit(1);}

    std::vector<std::string> tokens;
    boost::split (tokens, params_string, boost::is_any_of(delimiter), boost::token_compress_on);

    return tokens;
}
void openCloudPCD(string filename, PointCloudXYZ::Ptr cloud ){

    if (pcl::io::loadPCDFile<pcl::PointXYZ> (filename.c_str(), *cloud) == -1){
        PCL_ERROR ("Couldn't read cloud_source \n");
        exit(1);
    }
}
void m_crop(PointCloudXYZ::Ptr cloud, pcl::PointXYZ point,double radius,
                      PointCloudXYZ::Ptr  cloudOut){

   // parameters
    pcl::KdTreeFLANN<pcl::PointXYZ> kdtree;
    std::vector<int> pointIdxRadiusSearch;
    std::vector<float> pointRadiusSquaredDistance;
    kdtree.setInputCloud(cloud);


    // apply kdtree
    if (kdtree.radiusSearch(point, radius, pointIdxRadiusSearch, pointRadiusSquaredDistance)> 0){
        cloudOut->height = pointIdxRadiusSearch.size();
        cloudOut->points.resize(cloudOut->height);
        pcl::copyPointCloud<pcl::PointXYZ>(*cloud, pointIdxRadiusSearch, *cloudOut);
    }
    //*/

}
