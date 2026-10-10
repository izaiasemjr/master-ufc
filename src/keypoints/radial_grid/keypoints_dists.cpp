        
#include "./include/functions.hpp"

using namespace std;

#include<chrono>
using namespace std::chrono;

int main (int argc, char **argv)
    {
    
        /**
         ./keypoints_grid  -cloud bs039_N_N_0.pcd -keypoints bs039_N_N_0-key.pcd  -grid normal,15,11,11,6 -output bs039_N_N_0-grid.pcd -debug 1
        **/

        // GET PARAMETERS EXEMPLE:
        vector<string> clouds_str=get_parameters(argc,argv,"-cloud",",");
        vector<string> landmarks_str= get_parameters(argc,argv,"-keypoints",",");
        vector<string> grid_str = get_parameters(argc,argv,"-grid",",");
        vector<string> outputs_str = get_parameters(argc,argv,"-output",",");
        vector<string> debug_str = get_parameters(argc,argv,"-debug",",");

        // open Clouds pcd
        pcl::PointCloud<pcl::PointXYZ>::Ptr cloud(new pcl::PointCloud<pcl::PointXYZ>);
        openCloudPCD(clouds_str[0],cloud);
    
        // get keypoint noseTip (end of cloud)
        pcl::PointCloud<pcl::PointXYZ>::Ptr landmarks(new pcl::PointCloud<pcl::PointXYZ>);
        openCloudPCD(landmarks_str[0],landmarks);

        pcl::PointCloud<pcl::PointXYZ>::Ptr keypoints_grid(new pcl::PointCloud<pcl::PointXYZ>);
        auto start = chrono::steady_clock::now();
        gridkeyPointsFromNose(cloud,keypoints_grid,landmarks->points[13],grid_str);
        auto time_grid= std::chrono::duration<double>(chrono::steady_clock::now() - start).count()*1000;

        //saving file
        pcl::io::savePCDFile(outputs_str[0],*keypoints_grid);

        //saving time
        std::ofstream file;
        string filename;
        for (int i =0 ;i<grid_str.size();i++)
            filename += grid_str[i] + "_";
        filename += "times.dat";
        file.open(filename.c_str(), std::ios_base::app);
        file<<time_grid<<","<<clouds_str[0]<<endl;


        if(debug_str[0] == "1"){
            string  s = "pcl_viewer "+ outputs_str[0] + " " + clouds_str[0] +
                    " -ps 9 -ps 2 -fc  0,0,0  -fc 0,0,0 -bc 255,255,255";
            cout<<s<<endl;
            system(s.c_str());

            for (int k = 0;k<keypoints_grid->points.size();k++){
                pcl::PointCloud<pcl::PointXYZ>::Ptr keypoints_temp(new pcl::PointCloud<pcl::PointXYZ>);
                keypoints_temp->push_back(keypoints_grid->points[k]);
                auto dir = "../script/"  +clouds_str[0] + "_" + grid_str[0] + "_" + grid_str[1] + "/";
                system(("mkdir -p  " + dir).c_str());
                pcl::io::savePCDFile((dir +  to_string(k)+ ".pcd" ).c_str(),*keypoints_temp);
            }
        }

        return 0;
}
    

    
