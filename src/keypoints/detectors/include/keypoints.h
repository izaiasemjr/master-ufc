
#include "utils.h"
#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <pcl/keypoints/sift_keypoint.h>
#include <pcl/features/normal_3d_omp.h>
#include <pcl/keypoints/iss_3d.h>


// List the available keypoints
static const string SIFT_NORMAL  = "sift_normal";
static const string ISS  = "iss";
static const string SIFT_Z  = "sift_z";
static const string FROM_FILE = "fromFile";


using namespace std;


template<typename KeyPointT>
void getKeyPointsFromFile(string filename,
                          typename pcl::PointCloud<KeyPointT>::Ptr keypoints
                         ){

    pcl::io::loadPCDFile (filename.c_str(), *keypoints);

}


template<typename KeyPointT>
void getKeyPointsFromNose(string filename,
                          typename pcl::PointCloud<KeyPointT>::Ptr keypoints_choice
                         ){

    typename pcl::PointCloud<KeyPointT>::Ptr keypoints(new typename pcl::PointCloud<KeyPointT>);
    pcl::io::loadPCDFile (filename.c_str(), *keypoints);
    KeyPointT nose = keypoints->points[13];

    keypoints_choice->push_back(nose);
    keypoints_choice->push_back(KeyPointT(nose.x + 43.15,nose.y + 30.76,nose.z  -50.44)); // EYE_RIGHT_EXTERN
    keypoints_choice->push_back(KeyPointT(nose.x + 12.75,nose.y + 29.22,nose.z  -42.09)); // EYE_RIGHT_INTERN
    keypoints_choice->push_back(KeyPointT(nose.x - 50.45,nose.y + 26.77,nose.z  -45.81)); // EYE_LEFT_EXTERN
    keypoints_choice->push_back(KeyPointT(nose.x - 19.66,nose.y + 27.69,nose.z  -40.48)); // EYE_LEFT_INTERN
    keypoints_choice->push_back(KeyPointT(nose.x - 24.48,nose.y - 39.36,nose.z  -27.24)); // MOUTH_LEFT
    keypoints_choice->push_back(KeyPointT(nose.x + 25.27,nose.y - 36.84,nose.z  -29.99)); // MOUTH_RIGHT
    keypoints_choice->push_back(KeyPointT(nose.x + 0.63, nose.y - 29.12,nose.z  -12.6)); // MOUTH_CENTER_UP
    keypoints_choice->push_back(KeyPointT(nose.x + 1.23, nose.y - 44.05,nose.z  -14.51)); // MOUTH_CENTER_DOWN

}

template<typename PointT,typename KeyPointT>
void computeSiftNormal(typename pcl::PointCloud<PointT>::Ptr cloud,
                      typename pcl::PointCloud<KeyPointT>::Ptr cloud_keypoints,
                       pcl::PointCloud<Normal>::Ptr cloud_normals,
                      vector<string> params
                      ){

    using namespace pcl;



    float min_scale = stof(params[2]);
    int n_octaves = stoi(params[3]);
    int n_scales_per_octave = stoi(params[4]);
    float min_contrast = stof(params[5]);


////    Estimate the normals of the input cloud
//    PointCloud<Normal>::Ptr cloud_normals (new PointCloud<Normal>);;
//    estimateNormals<PointT>(cloud,cloud_normals,normal_radius);
//    cout<<"Normals computed: "<<cloud_normals->points.size()<<endl;

    // concat Points and Normals to form PointNormal object
    pcl::PointCloud<pcl::PointNormal>::Ptr cloud_normals_sift(new pcl::PointCloud<pcl::PointNormal>);
    pcl::concatenateFields (*cloud, *cloud_normals, *cloud_normals_sift);

    // Estimate the sift interest points using normals values from xyz as the Intensity variants
    SIFTKeypoint<PointNormal, PointWithScale> sift;
    PointCloud<PointWithScale>::Ptr keypoints(new PointCloud<PointWithScale>);
    search::KdTree<PointNormal>::Ptr tree(new search::KdTree<PointNormal> ());
    sift.setSearchMethod(tree);
    sift.setScales(min_scale, n_octaves, n_scales_per_octave);
    sift.setMinimumContrast(min_contrast);
    sift.setInputCloud(cloud_normals_sift);
    sift.compute(*keypoints);

    // copy cloud type PointWithScale to cloud XYZ
    copyPointCloud(*keypoints,*cloud_keypoints);

    // Sanity check
    if (keypoints->points.size() == 0 ){
      cout<<"0 zero keypoints computed, the program will finish"<<endl;
      exit(1);
    }

}

template<typename PointT,typename KeyPointT>
void computeSiftZ(typename pcl::PointCloud<PointT>::Ptr cloud,
                      typename pcl::PointCloud<KeyPointT>::Ptr cloud_keypoints,
                       pcl::PointCloud<Normal>::Ptr cloud_normals,
                      vector<string> params
                      ){

    using namespace pcl;



    float min_scale = stof(params[2]);
    int n_octaves = stoi(params[3]);
    int n_scales_per_octave = stoi(params[4]);
    float min_contrast = stof(params[5]);


////    Estimate the normals of the input cloud
//    PointCloud<Normal>::Ptr cloud_normals (new PointCloud<Normal>);;
//    estimateNormals<PointT>(cloud,cloud_normals,normal_radius);
//    cout<<"Normals computed: "<<cloud_normals->points.size()<<endl;

    // concat Points and Normals to form PointNormal object
    pcl::PointCloud<pcl::PointNormal>::Ptr cloud_normals_sift(new pcl::PointCloud<pcl::PointNormal>);
    pcl::concatenateFields (*cloud, *cloud_normals, *cloud_normals_sift);

    // Estimate the sift interest points using normals values from xyz as the Intensity variants
    SIFTKeypoint<PointNormal, PointWithScale> sift;
    PointCloud<PointWithScale>::Ptr keypoints(new PointCloud<PointWithScale>);
    search::KdTree<PointNormal>::Ptr tree(new search::KdTree<PointNormal> ());
    sift.setSearchMethod(tree);
    sift.setScales(min_scale, n_octaves, n_scales_per_octave);
    sift.setMinimumContrast(min_contrast);
    sift.setInputCloud(cloud_normals_sift);
    sift.compute(*keypoints);

    // copy cloud type PointWithScale to cloud XYZ
    copyPointCloud(*keypoints,*cloud_keypoints);

    // Sanity check
    if (keypoints->points.size() == 0 ){
      cout<<"0 zero keypoints computed, the program will finish"<<endl;
      exit(1);
    }

}


template<typename PointT,typename KeyPointT>
void computeISS(typename pcl::PointCloud<PointT>::Ptr cloud,
                      typename pcl::PointCloud<KeyPointT>::Ptr keypoints,
                      vector<string> params
                      ){


    double salientRadius = stof(params[1]);
    double nonMaxRadius = stof(params[2]);
    
    double threshold21 =  stof(params[3]);
    double threshold32 =  stof(params[4]);
    int minNeighbors =  stoi(params[5]);
    int numberOfThreads = stoi(params[6]);

    pcl::search::KdTree<PointXYZ>::Ptr tree (new pcl::search::KdTree<PointXYZ> ());
    pcl::ISSKeypoint3D<PointXYZ, PointXYZ> iss_detector;
    iss_detector.setSearchMethod (tree);
    iss_detector.setSalientRadius (salientRadius);
    iss_detector.setNonMaxRadius (nonMaxRadius);

    iss_detector.setThreshold21 (threshold21);
    iss_detector.setThreshold32 (threshold32);
    iss_detector.setMinNeighbors (minNeighbors);
    iss_detector.setNumberOfThreads (numberOfThreads);
    iss_detector.setInputCloud (cloud);
    iss_detector.compute (*keypoints);

}

template<typename PointT,typename KeyPointT>
void computeKeypoints(typename pcl::PointCloud<PointT>::Ptr& cloud,
                       typename pcl::PointCloud<KeyPointT>::Ptr& cloud_keypoints,
                       pcl::PointCloud<Normal>::Ptr normals,
                       vector<string> params
                    ){
    if(params.size()<1)
        cout<<"You should especify at least the methode name like: -keypoints sift_normal"<<endl;

    if (params[0]==SIFT_NORMAL){
        //cout<<"computing SIFT ..."<<endl;
        computeSiftNormal<PointT, KeyPointT>(cloud,cloud_keypoints,normals,params);
    }
     else if (params[0]==ISS){
       computeISS<PointT, KeyPointT>(cloud,cloud_keypoints,params);
    }
    else {
        cout<<"We not support this method. Methods Supported:"<<endl;
    }

}

