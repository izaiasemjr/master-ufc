        
#include "./include/functions.hpp"
    
using namespace std;

int main (int argc, char **argv)
    {
    
        /** example
        ./Crop -cloud bs000_N_N_0.pcd  -keypoints bs000_N_N_0-key.pcd  -crop_radius  80  -output  crop.pcd -offset 0,0,0 && pcl_viewer crop.pcd
        **/

        vector<string> clouds_str=get_parameters(argc,argv,"-cloud",",");
        vector<string> landmarks_str= get_parameters(argc,argv,"-keypoints",",");
        vector<string> crop_radius= get_parameters(argc,argv,"-crop_radius",",");
        vector<string> outputs = get_parameters(argc,argv,"-output",",");
        vector<string> offset = get_parameters(argc,argv,"-offset",",");
    
        // open Clouds pcd
        pcl::PointCloud<pcl::PointXYZ>::Ptr cloud(new pcl::PointCloud<pcl::PointXYZ>);
        openCloudPCD(clouds_str[0],cloud);
    
        // get keypoint noseTip (end of cloud)
        pcl::PointCloud<pcl::PointXYZ>::Ptr landmarks(new pcl::PointCloud<pcl::PointXYZ>);
        openCloudPCD(landmarks_str[0],landmarks);
        pcl::PointXYZ keypoint_source;
        if(landmarks_str.size()>1)
            keypoint_source = landmarks->points[stoi(landmarks_str[1])];
        else
            keypoint_source = landmarks->points[13];

        // Offset nose tip
        keypoint_source.x += stof(offset[0]);keypoint_source.y += stof(offset[1]);keypoint_source.z += stof(offset[2]);

        // crop
        double rcrop = stod(crop_radius[0]);
        pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_crop (new pcl::PointCloud<pcl::PointXYZ>);
        m_crop(cloud,keypoint_source,rcrop,cloud_crop);
    
    
        // save
        pcl::io::savePCDFileASCII (outputs[0].c_str(), *cloud_crop); // cloud full
       //*/
    

        return 0;
    }
    
    
    
    
    
