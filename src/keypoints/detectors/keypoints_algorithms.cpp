



#include "./include/utils.h"
#include "./include/keypoints.h"

#include<chrono>
using namespace std::chrono;

using namespace std;



int main (int argc, char **argv)
    {

        /**
        ./keypoints  -cloud bs039_N_N_0.pcd  -params sift_normal,10,4,7,8,0.0001 -output  bs039_N_N_0_sift.pcd -debug 1        
        **/

        // GET PARAMETERS EXEMPLE:
        vector<string> clouds_str=get_parameters(argc,argv,"-cloud",",");
        vector<string> params_str = get_parameters(argc,argv,"-params",",");
        vector<string> outputs_str = get_parameters(argc,argv,"-output",",");
        vector<string> debug_str = get_parameters(argc,argv,"-debug",",");


        // open Clouds pcd
        pcl::PointCloud<pcl::PointXYZ>::Ptr cloud(new pcl::PointCloud<pcl::PointXYZ>);
        openCloudPCD(clouds_str[0],cloud);

        // keypoints
        pcl::PointCloud<pcl::PointXYZ>::Ptr keypoints_out(new pcl::PointCloud<pcl::PointXYZ>);
        auto start = chrono::steady_clock::now();
        if(params_str[0]=="sift_normal"){
            PointCloudNormalPtr normals (new PointCloudNormal);
            estimateNormals<PointXYZ>(cloud,normals,stof(params_str[1]));
            computeSiftNormal<PointXYZ,PointXYZ>(cloud,keypoints_out,normals,params_str);
            pcl::io::savePCDFile(outputs_str[0],*keypoints_out);
        }
        else if (params_str[0]==ISS){
            computeISS<PointXYZ, PointXYZ>(cloud,keypoints_out,params_str);
            pcl::io::savePCDFile(outputs_str[0],*keypoints_out);
        }
        else{
            cout<<"method not implemented"<<endl;
            exit(1);
        }
        auto time= std::chrono::duration<double>(chrono::steady_clock::now() - start).count()*1000;


        //saving time
        std::ofstream file;
        string filename;
        for (int i =0 ;i<params_str.size();i++)
            filename += params_str[i] + "_";
        filename += "times.dat";
        file.open(filename.c_str(), std::ios_base::app);
        file<<time<<","<<clouds_str[0]<<endl;
    

        if(debug_str[0] == "1"){
            string  s = "pcl_viewer "+ outputs_str[0] + " " + clouds_str[0] +
                    " -ps 8 -ps 2 -fc  0,0,0  -fc 0,0,0 -bc 255,255,255";
            cout<<s<<endl;
            system(s.c_str());
        }

        return 0;
}
    

    
