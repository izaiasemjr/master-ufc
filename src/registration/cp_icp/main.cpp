
#include "./include/izaias_functions.hpp"



int main (int argc, char **argv)
{

    cout<<"Init CP-ICP!"<<endl;
    int start_s,stop_s;

    /// GET PARAMETERS ////////////////////////////////////////////////////////////////////////
    vector<string> path_str = get_parameters(argc,argv,"-path",",");
    vector<string> person_str = get_parameters(argc,argv,"-person",",");
    vector<string> source_str = get_parameters(argc,argv,"-source",",");
    vector<string> target_str = get_parameters(argc,argv,"-target",",");
    vector<string> target_special_str = get_parameters(argc,argv,"-target_special",","); //global_reference
    vector<string> icp_str = get_parameters(argc,argv,"-icp",",");
    vector<string> k_str = get_parameters(argc,argv,"-k",",");
    vector<string> field_str = get_parameters(argc,argv,"-field",",");
    vector<string> th_occlusion_str = get_parameters(argc,argv,"-th",",");
    vector<string> outputs_str = get_parameters(argc,argv,"-outputs",",");
    vector<string> penality_str = get_parameters(argc,argv,"-penality",",");
    vector<string> debug_str = get_parameters(argc,argv,"-debug",",");
    vector<string> occlusion_str = get_parameters(argc,argv,"-occlusion",",");
    vector<string> ground_truth_str = get_parameters(argc,argv,"-GT",",");
    vector<string> th_restoration_str = get_parameters(argc,argv,"-th_rest",",");

    int k = stoi(k_str[0]);
    int debug = stoi(debug_str[0]);


    /// OPEN CLOUDS ///////////////////////////////////////////////////////////////////////////
    PointCloudXYZPtr cloud_source(new PointCloudXYZ);
    openCloudPCD(path_str[0] +person_str[0] + "/" + person_str[0] + "_" + source_str[0] + ".pcd",cloud_source);
    PointCloudXYZPtr cloud_target(new PointCloudXYZ);
		if(target_special_str[0] == "null")
			openCloudPCD(path_str[0] +person_str[0] + "/" + person_str[0] + "_" +  target_str[0] + ".pcd",cloud_target);
		else
 			openCloudPCD(target_special_str[0],cloud_target);


    /// APPLY CLOUD PARTITION IN X,Y,Z ////////////////////////////////////////////////////////
    start_s=clock();
    int n_axis = field_str.size();
    vector<PointCloudXYZPtr> source_partition_current[n_axis];
    vector<PointCloudXYZPtr> target_partition_current[n_axis];
    std::valarray<double> arrayRMSEs(k*n_axis);
    vector<Eigen::Matrix4f> MATs;

    // iterate 3 times (x,y,z)
    for(int i=0;i<n_axis;i++){
        source_partition_current[i] = cloudPartitioning(cloud_source,k,field_str[i]);
        target_partition_current[i] = cloudPartitioning(cloud_target,k,field_str[i]);

        // Icp by each   partition
        PointCloudXYZ regist_partition ;
        pcl::IterativeClosestPoint<PointXYZ, PointXYZ> icp_result;
        for(int j=0;j<k;j++){

             // apply icp
            icp_pcl(source_partition_current[i][j],target_partition_current[i][j],regist_partition,
                    stod(icp_str[0]),stod(icp_str[1]),icp_result);

            // Get RMSE,Matrix, cloud regist
            arrayRMSEs[(k*i)+j]=icp_result.getFitnessScore();
            MATs.push_back(icp_result.getFinalTransformation());
            if(debug){cout<<"RMSE: "<<icp_result.getFitnessScore()<<" field: "<<field_str[i]<<endl;}


        }


    }
    // Get index of min and max RMSE ( idx[0]=min, idx[1]=max )
    int *idx= getIdxMinMax(arrayRMSEs);
    if(debug){cout<<"idx min rmse: "<<idx[0]<<"\n"<<"idx max rmse: "<<idx[1]<<endl;}


    /// TRANSFORM FULL FACE  //////////////////////////////////////////////////////////////////
    PointCloudXYZPtr cloud_source_regist(new PointCloudXYZ);
    pcl::transformPointCloud (*cloud_source, *cloud_source_regist,MATs[idx[0]]);
    pcl::io::savePCDFileASCII (outputs_str[0].c_str(), *cloud_source_regist);


    // save part cloud to TRAIN-TEST with missing parts (junior)
    if(source_str[0] == "N_N_0"){
        int aux =0;
        for(int i=0;i<n_axis;i++){
            for(int j=0;j<k;j++){
                string outputPart = outputs_str[7]+ string("_") + to_string(aux) + ".pcd";
                PointCloudXYZPtr cloud_part_regist(new PointCloudXYZ);
                pcl::transformPointCloud (*source_partition_current[i][j], *cloud_part_regist,MATs[idx[0]]);
                savePCD(outputPart.c_str(), cloud_part_regist);
                aux++;
            }
        }
    }
    else if(source_str[0][0] == 'O') {
        string outputPart = outputs_str[7] + string("_0")  + ".pcd";
        PointCloudXYZPtr cloud_part_regist(new PointCloudXYZ);
        pcl::transformPointCloud (*source_partition_current[idx[0]/2][idx[0]%2], *cloud_part_regist,MATs[idx[0]]);
        savePCD(outputPart.c_str(), cloud_part_regist);
    }


    // save matrix
    print4x4Matrix(outputs_str[3], MATs[idx[0]]);
    if(debug){cout<<"Transformation ok"<<endl;}

    // debug RMSE
    double RMSE_global_before_icp= get_RMSE(cloud_source,cloud_target,std::numeric_limits<double>::max());
    double RMSE_global_after_icp= get_RMSE(cloud_source_regist,cloud_target,std::numeric_limits<double>::max());
    if(debug){
        cout<<"RMSE global before: "<<RMSE_global_before_icp<<endl;
        cout<<"RMSE global after: "<< RMSE_global_after_icp<<endl;
    }

    /// OCCLUSION LOCALIZATION ///////////////////////////////////////////////////////////////
    if(stoi(occlusion_str[0])==1){
        // penality
        PointCloudXYZPtr cloud_occlusion(new PointCloudXYZ);
        PointCloudXYZPtr cloud_occlusion_removed(new PointCloudXYZ);
        double RMSE_no_occlusion = get_points_RMSE(cloud_source_regist,cloud_target,cloud_occlusion,cloud_occlusion_removed,stod(th_occlusion_str[0]),stoi(penality_str[0]));
        savePCD(outputs_str[4].c_str(), cloud_occlusion_removed);

        // time
        stop_s=clock();
        double time =((stop_s-start_s)/double(CLOCKS_PER_SEC));
        if(debug){cout<<"time: "<<time<<endl;}

        // GET PART OCCLUSION ON TARGET
        // methode inverse
        PointCloudXYZPtr cloud_occlusion_restored_inverse(new PointCloudXYZ);
        double th = stod(th_restoration_str[0]);
        get_restored_occlusion2(cloud_target,cloud_occlusion,cloud_occlusion_restored_inverse,th);
        *cloud_occlusion_restored_inverse+=*cloud_occlusion_removed;
        //savePCD("cloud_occlusion_restored_inverse.pcd",cloud_occlusion_restored_inverse);
        savePCD(outputs_str[5].c_str(), cloud_occlusion_restored_inverse);

        // methode direct (lembrar que aqui o target é modificado devido a remoção de pontos)
        PointCloudXYZPtr cloud_occlusion_restored(new PointCloudXYZ);
        *cloud_occlusion_restored+=*cloud_occlusion_removed;
        get_restored_occlusion(cloud_occlusion,cloud_target,cloud_occlusion_restored);
        //savePCD("cloud_occlusion_restored.pcd",cloud_occlusion_restored);
        savePCD(outputs_str[6].c_str(), cloud_occlusion_restored);


        // Occlusion output colored (visualiazation)
        PointCloudXYZRGBPtr cloud_source_occlusion_rgb (new PointCloudXYZRGB);
        *cloud_source_occlusion_rgb = xyz_2_xyzrgb(cloud_source_regist,255,0,0);
        PointCloudXYZRGBPtr cloud_remaining_rgb (new PointCloudXYZRGB);
        *cloud_remaining_rgb = xyz_2_xyzrgb(cloud_occlusion,0,255,0);
        *cloud_source_occlusion_rgb+=*cloud_remaining_rgb; //concatenation
        pcl::io::savePCDFileASCII (outputs_str[1].c_str(), *cloud_source_occlusion_rgb);

        /// BUILD TABLE DATA FORN ANALYSE (CSV) //////////////////////////////////////////////////////////////
        // get metricas (TP, FN, FP, TN)
        int TP=0,FN=0,FP=0,TN=0;
        PointCloudXYZPtr cloud_GT(new PointCloudXYZ);

        // calcula metricas somente se tem ground truth
        if(ground_truth_str[0].compare("null")){
            // transform ground truth
            openCloudPCD(ground_truth_str[0] + person_str[0] + "/" + person_str[0] + "_" + source_str[0] + ".pcd",cloud_GT);
            pcl::transformPointCloud (*cloud_GT, *cloud_GT, MATs[idx[0]]);
            // get metricas
            getMetricas(cloud_GT,cloud_source_regist,cloud_occlusion,TP,FN,FP,TN);
        }
        if(debug){
            cout<<"TP: "<<TP<<"\nFN: "<<FN<<"\nFP: "<<FP<<"\nTN: "<<TN<<endl;
            cout<<"Cloud Full: "<<cloud_source_regist->points.size()<<endl;
            cout<<"Oclusão GT: "<<cloud_GT->points.size()<<endl;
            cout<<"Occlusion detection: "<<cloud_occlusion->points.size()<<endl;
        }

        // RMSEs Relations
        double lambda1 = RMSE_global_after_icp/RMSE_global_before_icp;
        double lambda2 = RMSE_no_occlusion/RMSE_global_after_icp;
        if(debug){
            cout<<"RMSE no occlusion: "<<RMSE_no_occlusion<<endl;
        }


        // save data in csv
        string sys="echo " + person_str[0] + " "  +  source_str[0] + " cp-icp " + penality_str[0] +  " "
                           + to_string(TP) + " " + to_string(FN) + " " + to_string(FP) + " " + to_string(TN) + " "
                           + to_string(RMSE_global_after_icp)  + " " + to_string(lambda1) + " " + to_string(lambda2) + " "
                           + to_string(time) + " >> " +  outputs_str[2].c_str();

		  system(sys.c_str());
    }



    return 0;
}
