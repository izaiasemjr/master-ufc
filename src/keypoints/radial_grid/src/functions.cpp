/*
 * by
 * Izaias Junior
 * Interfaces Group - UFC
 */


#include "../include/functions.hpp"
#include <boost/algorithm/string.hpp>
#define PI 3.14159265


using namespace std;





void gridkeyPointsFromNose(PointCloudXYZPtr cloud,
                          PointCloudXYZPtr keypoints,
                          PointXYZ ref,
                          vector<string> grid_str
                           ){

    float teta = stof(grid_str[1]);
    float r_initial= stof(grid_str[2]);
    float r_step = stof(grid_str[3]);
    int n_sectors = stoi(grid_str[4]);

    PointCloudXYZPtr keypoints_plane (new PointCloudXYZ);

     // grid in plane of nose
    keypoints_plane->push_back(ref);
    float r = r_initial;
    for(int i = 0;i<n_sectors;i++){
        for(int j=0;j<360/teta;j++){


            if(grid_str[0]== "normal"){
               teta = stof(grid_str[1]);
            }
            else if(grid_str[0]== "sparse"){
               if(i>=0 && i<3) 
                    teta = 60 - i*20;
                else
                   teta = stof(grid_str[1]);
            }else{
                cout<<"method diferrent of sparse or normal"<<endl;
                exit(1);
            }

            float angle = j*teta*(PI/180.0);
            keypoints_plane->push_back(PointXYZ(ref.x + r*cos(angle), ref.y + r*sin(angle), ref.z));

        }
        r+=r_step;
    }


    // make cloud in same plane of nose
    PointCloudXYZPtr cloud_plane (new PointCloudXYZ);
    pcl::copyPointCloud(*cloud,*cloud_plane);
    for(int i=0;i<cloud_plane->points.size();i++){
        cloud_plane->points[i].z=ref.z;
    }


    // find keypoints
    pcl::search::KdTree<pcl::PointXYZ> tree;
    tree.setInputCloud(cloud_plane);
    vector<float> dist;
    vector<int> idx;
    for (int i =0;i<keypoints_plane->points.size();++i){
        tree.nearestKSearch(keypoints_plane->points [i],1, idx,dist);
        keypoints->push_back(PointXYZ(cloud_plane->points[idx[0]].x,cloud_plane->points[idx[0]].y,cloud->points[idx[0]].z));
    }


}


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

const vector<string> explode(const string& s, const char& c)
{
    string buff{""};
    vector<string> v;

    for(auto n:s)
    {
        if(n != c) buff+=n; else
        if(n == c && buff != "") { v.push_back(buff); buff = ""; }
    }
    if(buff != "") v.push_back(buff);

    return v;
}
