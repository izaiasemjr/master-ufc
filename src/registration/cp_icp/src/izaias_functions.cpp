/*
 * by
 * Izaias Junior
 * Interfaces Group - UFC
 */


#include "../include/izaias_functions.hpp"
#include <boost/algorithm/string.hpp>
#include <cmath>


// COMMONS
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
void savePCD(const char* path,PointCloudXYZPtr cloud){
    cloud->width=cloud->points.size();
    cloud->height = 1;
    pcl::io::savePCDFileASCII (path, *cloud);
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
pcl::PointXYZ get_noseTip_lm3(string file_path){


    bool flag_nose = false;
    std::vector<pcl::PointXYZ> points;
    std::vector<double> elements;
    elements.clear();

    // open file
    std::ifstream Stream(file_path.c_str(), std::ios::in);
    if(Stream.is_open()){
        //cout<<"open file..."<<endl;
        std::string Line = "";
        std::string word = "";

        // get line
        while(getline(Stream, Line,'\n')){

            if(flag_nose){
                std::stringstream line(Line);
                while(std::getline(line, word,' ')){
                    float value;
                    std::stringstream(word)>>value;
                    elements.push_back(value);
                }

                //get points
                points.push_back(pcl::PointXYZ(elements[0],elements[1],elements[2]));
                elements.clear();
                flag_nose=false;
            }
            if (/*Line.find("nose") != std::string::npos ||*/ Line.find("Nose tip") != std::string::npos ) {
                //cout<<Line<<endl;
                flag_nose=true;
            }

        }
        Stream.close();
    }
    else{
        cout<<"Impossible to open %s. Are you in the right directory ? !\n"<< file_path<<endl;
        getchar();
    }




    return  points[0];
}

void icp_pcl(PointCloudXYZPtr cloud_source,
                        PointCloudXYZ::Ptr cloud_target,
                        PointCloudXYZ& cloud_source_regist,
                        double transf_epsilon,int max_it,
                        pcl::IterativeClosestPoint<PointXYZ, PointXYZ>& icp
                        ){

    icp.setTransformationEpsilon (transf_epsilon);
    icp.setMaximumIterations (max_it);

    icp.setInputSource(cloud_source);
    icp.setInputTarget(cloud_target);
    icp.align(cloud_source_regist);

}
void icp_pcl(PointCloudXYZPtr cloud_source,
                        PointCloudXYZ::Ptr cloud_target,
                        PointCloudXYZ& cloud_source_regist,
                        double transf_epsilon,int max_it,int max_distance,
                        pcl::IterativeClosestPoint<PointXYZ, PointXYZ>& icp
                        ){
    icp.setMaxCorrespondenceDistance(max_distance);
    icp.setTransformationEpsilon (transf_epsilon);
    icp.setMaximumIterations (max_it);

    icp.setInputSource(cloud_source);
    icp.setInputTarget(cloud_target);
    icp.align(cloud_source_regist);

}



int* getIdxMinMax(std::valarray<double> array){
    int *idx = new int [2];

    for(int i=0;i<array.size();++i){
        if(array[i]==array.min())
            idx[0]=i;
        if(array[i]==array.max())
            idx[1]=i;
    }
    return idx;
}

void print4x4Matrix (string path,const Eigen::Matrix4f & matrix){
  string out =  to_string(matrix (0, 0)) + " " +to_string(matrix (0, 1)) + " " +  to_string(matrix (0, 2)) + " " +  to_string(matrix (0, 3)) + "\n"
              + to_string(matrix (1, 0)) + " " +to_string(matrix (1, 1)) + " " +  to_string(matrix (1, 2)) + " " +  to_string(matrix (1, 3)) + "\n"
              + to_string(matrix (2, 0)) + " " +to_string(matrix (2, 1)) + " " +  to_string(matrix (2, 2)) + " " +  to_string(matrix (2, 3)) + "\n"
              + to_string(matrix (3, 0)) + " " +to_string(matrix (3, 1)) + " " +  to_string(matrix (3, 2)) + " " +  to_string(matrix (3, 3));

  string command = "echo \" " + out +  " \" >  " + path ;
  system(command.c_str());

}


// CLOUD PRTITIONTING
bool comparePointX(pcl::PointXYZ p1, pcl::PointXYZ p2) {

    if ( p1.x<p2.x) { //
        return true;
    }
    else{
        return false;
    }
}
bool comparePointY(pcl::PointXYZ p1, pcl::PointXYZ p2) {

    if ( p1.y<p2.y) { //
        return true;
    }
    else{
        return false;
    }
}
bool comparePointZ(pcl::PointXYZ p1, pcl::PointXYZ p2) {

    if ( p1.z<p2.z) { //
        return true;
    }
    else{
        return false;
    }
}
std::vector<PointCloudXYZPtr> cloudPartitioning(PointCloudXYZPtr cloud, int n, string field){


    //float s = cloud->width;
    float s = (cloud->width == 1) ? cloud->height : cloud->width ;   // robustez
    float num = floor(s/n);

    // Switch by field
    if(!field.compare("x")){
        std::sort(cloud->points.begin(),cloud->points.end(),comparePointX);
        //cout<<"field x"<<endl;
    }
    else if(!field.compare("y")){
        std::sort(cloud->points.begin(),cloud->points.end(),comparePointY);
        //cout<<"field y"<<endl;

    }
    else if(!field.compare("z")){
        std::sort(cloud->points.begin(),cloud->points.end(),comparePointZ);
        //cout<<"field z"<<endl;
    }
    else{
        cout<<"Axis not supported, exiting ..."<<endl;
        exit(1);
    }

    //Creating subclouds
    vector<PointCloudXYZPtr> sn;
    for(int j=0;j<n;j++){

        PointCloudXYZPtr sn1 (new PointCloudXYZ);
        sn1->width = num;
        sn1->height = 1;

        for(int i=j*num ; i<(j+1)*num ; i++){
            sn1->points.push_back(cloud->points[i]);
        }
        sn.push_back(sn1);

    }

    return sn;
}

// RMSE
double get_points_RMSE(PointCloudConstPtr source, PointCloudConstPtr target,
                       PointCloudXYZPtr cloud_occlusion, PointCloudXYZPtr cloud_occlusion_removed,
                       double dist_thr, int penality ){

    // clean RMSEs
    double MSE_no_occlusion;
    int aux=0;

    // verify if clouds are epmty
    if(source->points.empty() || target->points.empty()){
        exit(1);
    }

    // Build KDTree
    pcl::search::KdTree<pcl::PointXYZ>::Ptr tree(new pcl::search::KdTree<pcl::PointXYZ>);
    tree->setInputCloud(target);

    // index and distances from correspondences
    std::vector<int> nn_indices (1);
    std::vector<float> nn_dists (1);

    for (size_t i = 0; i < source->points.size (); ++i){

        //Avoid NaN points as they crash nn searches
        if(!std::isfinite((*source)[i].x)){
            continue;
        }

        // Search
        tree->nearestKSearch(source->points[i], 1, nn_indices, nn_dists);

        // Penality
        double dist2=pow(source->points[i].x - target->points[nn_indices[0]].x,2)+
                    pow(source->points[i].y - target->points[nn_indices[0]].y,2)+
                    pow(source->points[i].z - target->points[nn_indices[0]].z,2);

        double distZ=source->points[i].z - target->points[nn_indices[0]].z;
        double new_dist2=dist2;
        if (penality)
            new_dist2 = z_penality(distZ,dist2);

        // Threshold
        if (new_dist2 >  dist_thr*dist_thr){
            //pega os pontos que tem grandes distâncias ao seu vizinho mais próximo
            cloud_occlusion->points.push_back(source->points[i]);
        }
        else{
             // calcula o RMSE sem os pontos que ocluem a face
             MSE_no_occlusion+=new_dist2;
             cloud_occlusion_removed->points.push_back(source->points[i]);
             aux++;
        }

    }

    return sqrt(MSE_no_occlusion/aux);


}

bool verifyPointInCloud(PointCloudXYZPtr cloud , PointXYZ point){

    for (size_t i = 0; i < cloud->points.size (); ++i){
        if( (cloud->points[i].x == point.x) && (cloud->points[i].y == point.y) && (cloud->points[i].z == point.z) )
            return true;
    }

    return false;
}

double nearestSearch(PointCloudXYZPtr cloud , PointXYZ point){

    int idx=0;
    double current_dist=0;
    double dist_min= numeric_limits<double>::max();
    for (size_t i=0;i<cloud->points.size ();++i){
        current_dist =  pow(cloud->points[i].x -  point.x,2)+
                        pow(cloud->points[i].y - point.y,2)+
                        0*(pow(cloud->points[i].z - point.z,2));

        if(current_dist<dist_min){
            dist_min=current_dist;
            idx=i;
        }
    }

    return idx;
}

bool removePointInCloud(PointCloudXYZPtr cloud , int pos_remove){

    int aux=0;
    auto it = cloud->points.begin();
    for(it;it!=cloud->points.end();it++){
        if(pos_remove==aux){
            cloud->points.erase(it);
            return true;
        }
    aux++;
    }

    return false;
}

void get_restored_occlusion(PointCloudXYZPtr cloud_source,PointCloudXYZPtr cloud_target,
                            PointCloudXYZPtr cloud_result){

    // k nearest to search
    int k_nearest=2;

    // verify if clouds are epmty
    if(cloud_target->points.empty() || cloud_source->points.empty()){
        exit(1);
    }

    // Build KDTree
    pcl::search::KdTree<pcl::PointXYZ>::Ptr tree(new pcl::search::KdTree<pcl::PointXYZ>);
    tree->setInputCloud(cloud_target);

    // index and distances from correspondences
    std::vector<int> nn_indices (k_nearest);
    std::vector<float> nn_dists (k_nearest);

    int idx_nearest=0;
    // iterate from source
    for (size_t i = 0; i <cloud_source->points.size (); ++i){

        //Avoid NaN points as they crash nn searches
        if(!std::isfinite((*cloud_source)[i].x)){
            continue;
        }

        /*/ Search
        tree->nearestKSearch(cloud_source->points[i], k_nearest, nn_indices, nn_dists);
        cloud_result->points.push_back(cloud_target->points[nn_indices[0]] );
        removePointInCloud(cloud_target,nn_indices[0]);
        tree->setInputCloud(cloud_target);
        //*/

        //cout<<"\nsize before: "<<cloud_target->points.size()<<endl;
        idx_nearest=nearestSearch(cloud_target,cloud_source->points[i]);

        cloud_result->points.push_back(cloud_target->points[idx_nearest]);
        //removePointInCloud(cloud_target,idx_nearest);
        //cout<<"size after: "<<cloud_target->points.size()<<endl;



    }


}


void get_restored_occlusion2(PointCloudXYZPtr cloud_source,PointCloudXYZPtr cloud_target,
                            PointCloudXYZPtr cloud_result,double th){

    // k nearest to search
    int k_nearest=1;

    // verify if clouds are epmty
    if(cloud_target->points.empty() || cloud_source->points.empty()){
        exit(1);
    }

    // Build KDTree
    pcl::search::KdTree<pcl::PointXYZ>::Ptr tree(new pcl::search::KdTree<pcl::PointXYZ>);
    tree->setInputCloud(cloud_target);

    // index and distances from correspondences
    std::vector<int> nn_indices (k_nearest);
    std::vector<float> nn_dists (k_nearest);

    int idx_nearest=0;
    // iterate from source
    for (size_t i = 0; i <cloud_source->points.size (); ++i){

        //Avoid NaN points as they crash nn searches
        if(!std::isfinite((*cloud_source)[i].x)){
            continue;
        }


        //
        idx_nearest=nearestSearch(cloud_target,cloud_source->points[i]);
        double dist = pow(cloud_source->points[i].x -  cloud_target->points[idx_nearest].x,2)+
                      pow(cloud_source->points[i].y -  cloud_target->points[idx_nearest].y,2)+
                   0*(pow(cloud_source->points[i].z -  cloud_target->points[idx_nearest].z,2));

        if(dist< th)
            cloud_result->points.push_back(cloud_source->points[i]);


        //removePointInCloud(cloud_target,idx_nearest);
        //*/
    }


}


double z_penality(double distz , double dist){

    if(distz>=0){
        return dist;
    }
    else if (distz<0){
        return pow(2,-1*dist);
    }
}
double get_RMSE(PointCloudConstPtr m_source, PointCloudConstPtr m_target,double dist_thr){

    // clean RMSEs
    double SumD2=0;
    int aux=0;

    PointCloudConstPtr source; source = m_source;
    PointCloudConstPtr target; target = m_target;

    // calc RMSE using smaller cloud
    if(target->points.size() < source->points.size()){
        source = m_target;
        target = m_source;
    }

    // verify if clouds are epmty
    if(source->points.empty() || target->points.empty()){
        exit(1);
    }

    // Build KDTree
    pcl::search::KdTree<PointXYZ>::Ptr tree(new pcl::search::KdTree<PointXYZ>);
    tree->setInputCloud(target);

    // index and distances from correspondences
    std::vector<int> nn_indices (1);
    std::vector<float> nn_dists (1);

    for (size_t i = 0; i < source->points.size (); ++i){

        //Avoid NaN points as they crash nn searches
        if (!std::isfinite(source->points[i].x) || !std::isfinite(source->points[i].y) || !std::isfinite(source->points[i].z))
        continue;

        // Search
        tree->nearestKSearch (source->points[i], 1, nn_indices, nn_dists);

        // Threshold
        if (nn_dists[0] < dist_thr){
            SumD2= SumD2 + (nn_dists[0]);
            aux++;
        }


    }

    return sqrt(SumD2/aux);


}



// METRICAS
bool compareValues(float a,float b, float epsilon ){
    return (fabs(a-b) < epsilon);
}
bool comparePoints(PointXYZ p1,PointXYZ p2, float eps ){
    return (compareValues(p1.x,p2.x,eps)  && compareValues(p1.y,p2.y,eps) && compareValues(p1.z,p2.z,eps));
}
PointCloudXYZPtr getLiers(PointCloudConstPtr global , PointCloudConstPtr truth){

    PointCloudXYZPtr liers (new PointCloudXYZ);
    int isTruth=0;

    // Find False positive
    for(int i=0;i<global->points.size();i++){
        for(int j=0;j<truth->points.size();j++){
            if(comparePoints(global->points[i],truth->points[j],0.00001)){
               isTruth=1;
            }
        }

        // se esse ponto não é da verdade terreste ele é da mentira terrestre
        if(!isTruth){
            liers->points.push_back(global->points[i]);
        }
        isTruth=0;
    }

    return liers;

}
void getMetricas(PointCloudConstPtr cloud_GT,PointCloudConstPtr cloud_source_regist,
                 PointCloudConstPtr cloud_remaining,
                 int& TP,int& FN,int& FP,int& TN){

    // Find truth positive
    for(int i=0;i<cloud_remaining->points.size();i++){
        for(int j=0;j<cloud_GT->points.size();j++){
            if(comparePoints(cloud_remaining->points[i],cloud_GT->points[j], 0.000001)){
               TP++;
            }
        }
    }

    // FN Complement TP
    FN = cloud_GT->points.size() - TP;

    // get "ground lier"
    PointCloudXYZPtr liers = getLiers(cloud_source_regist,cloud_GT);

    // Find False positive
    for(int i=0;i<cloud_remaining->points.size();i++){
        for(int j=0;j<liers->points.size();j++){
            if(comparePoints(cloud_remaining->points[i],liers->points[j],0.00001)){
               FP++;
            }
        }
    }

    // TN Complement TP
    TN = liers->points.size() - FP;

    //*/


}




//VIZUALIZATION
PointCloudXYZRGB xyz_2_xyzrgb(PointCloudXYZPtr cloud, int R, int G, int B ){
    PointCloudXYZRGB cloud_xyzrgb;
    copyPointCloud(*cloud, cloud_xyzrgb);

    cloud_xyzrgb.points.resize( cloud->size());
    uint8_t r = /*rand() % 255 + 50*/ R;
    uint8_t g = /*rand() % 255 + 50*/ G;
    uint8_t b = /*rand() % 255 + 50*/ B ;

    for (size_t i = 0; i < cloud->points.size(); i++) {
       cloud_xyzrgb.points[i].x = cloud->points[i].x;
       cloud_xyzrgb.points[i].y = cloud->points[i].y;
       cloud_xyzrgb.points[i].z = cloud->points[i].z;
             cloud_xyzrgb.points[i].r = r;
             cloud_xyzrgb.points[i].g = g;
             cloud_xyzrgb.points[i].b = b;
    }
    return cloud_xyzrgb;
}
