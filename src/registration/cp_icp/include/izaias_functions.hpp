/*by
 * Izaias Junior
 * Interfaces Group - UFC
 */


// basics PCL manipulations
#include <pcl/io/pcd_io.h>
#include <pcl/point_types.h>
#include <pcl/console/parse.h>


// PCL algorithms
#include <pcl/kdtree/kdtree_flann.h>

#include <pcl/registration/ia_ransac.h>
#include <pcl/registration/icp.h>

#include <pcl/filters/passthrough.h>

// C++
#include <valarray>
#include <ctime>
/*/
#include <stdlib.h> //for using system calls
#include <ios>
#include <fstream>
//*/

using namespace std;


typedef pcl::PointXYZ PointXYZ;
typedef pcl::PointCloud<PointXYZ>::Ptr PointCloudXYZPtr;
typedef pcl::PointCloud<PointXYZ> PointCloudXYZ;
typedef pcl::PointCloud<pcl::PointXYZ>::ConstPtr PointCloudConstPtr;
typedef pcl::PointXYZRGB PointXYZRGB;
typedef pcl::PointCloud<PointXYZRGB> PointCloudXYZRGB;
typedef pcl::PointCloud<PointXYZRGB>::Ptr PointCloudXYZRGBPtr;



// CLASSES3

//
class PartPC {

    public:
        // attributes
        int level;
        PointXYZ refCenter;
        PointCloudXYZPtr parentPC;
        std::vector<PartPC> partPCs;

        //constructor
        PartPC(int level, PointCloudXYZPtr parentPC,PointXYZ refCenter ){
            this->level = level;
            this->refCenter = refCenter;

            this->parentPC =parentPC;
            //pcl::PointCloud<pcl::PointXYZ>::Ptr new_cloud(parentPC);
            //this->parentPC=new_cloud;
            //pcl::copyPointCloud(*parentPC,*(this->parentPC));

            partPCs.reserve(4);
        }
        // constructor overload
        PartPC(int level, PointCloudXYZPtr parentPC ){
            this->level=level;
            this->parentPC=parentPC;
            //pcl::PointCloud<pcl::PointXYZ>::Ptr new_cloud(parentPC);
            //this->parentPC;
            //pcl::copyPointCloud(*parentPC,*(this->parentPC));

            this->refCenter=get_centroid(this->parentPC); // default reference is centroid
            partPCs.reserve(4);
        }

        // methodes
        int getLevel(){
               return this->level;
            }
        PointCloudXYZPtr getParentPC(){
            return parentPC;
        }
        PointXYZ getRefCenter(){
            return refCenter;
        }
        std::vector<PartPC> getPartPCs(){
            return partPCs;
        }

        PointXYZ get_centroid(pcl::PointCloud<pcl::PointXYZ>::Ptr cloud){
            Eigen::Vector4f centroid;
            pcl::compute3DCentroid(*cloud,centroid);
            return pcl::PointXYZ(centroid[0],centroid[1],centroid[2]);
        }

        pcl::PointCloud<pcl::PointXYZ>::Ptr filterPlane(pcl::PointCloud<pcl::PointXYZ>::Ptr cloud
                                                        ,string field, float min, float max){
            pcl::PassThrough<pcl::PointXYZ> pass;
            pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_filtered(new pcl::PointCloud<pcl::PointXYZ>);

            // filtering
           pass.setInputCloud(cloud);
           pass.setFilterFieldName(field);
           pass.setFilterLimits(min, max);
           pass.filter(*cloud_filtered);
           return cloud_filtered;
        }

        // methodes
        void execute(){

            pcl::PassThrough<pcl::PointXYZ> pass;
            pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_filtered(new pcl::PointCloud<pcl::PointXYZ>);

            pcl::PointCloud<pcl::PointXYZ>::Ptr cloud = getParentPC();
            PointXYZ point_reference = getRefCenter();

            for(int i=0;i<4;i++){
                switch(i){
                    case 0:
                        {
                        cloud_filtered = pcl::PointCloud<pcl::PointXYZ>::Ptr (new pcl::PointCloud<pcl::PointXYZ>);
                         // filtering target in x
                        pass.setInputCloud(cloud);
                        pass.setFilterFieldName("x");
                        pass.setFilterLimits(point_reference.x, numeric_limits<float>::max());
                        pass.filter(*cloud_filtered);

                        // filtering target in y
                        pass.setInputCloud(cloud_filtered);
                        pass.setFilterFieldName("y");
                        pass.setFilterLimits(point_reference.y, numeric_limits<float>::max());
                        pass.filter(*cloud_filtered);

                        // update and  recursivity
                        partPCs.push_back(PartPC(getLevel()-1,cloud_filtered));
                        if(getLevel()>1){
                            partPCs[i].execute();
                        }
                        // save
                        string s = string("./data_cups/cloud_") + to_string(getLevel()) + "_" + to_string(i)  + ".pcd" ;
                        //pcl::io::savePCDFileASCII(s,*cloud_filtered);
                        break;
                        }
                    case 1:
                        {
                        cloud_filtered = pcl::PointCloud<pcl::PointXYZ>::Ptr (new pcl::PointCloud<pcl::PointXYZ>);
                        // filtering target in x
                        pass.setInputCloud(cloud);
                        pass.setFilterFieldName("x");
                        pass.setFilterLimits(-numeric_limits<float>::max(),point_reference.x);
                        pass.filter(*cloud_filtered);
                        // filtering target in y
                        pass.setInputCloud(cloud_filtered);
                        pass.setFilterFieldName("y");
                        pass.setFilterLimits(point_reference.y, numeric_limits<float>::max());
                        pass.filter(*cloud_filtered);
                        // update
                        partPCs.push_back( PartPC(getLevel()-1,cloud_filtered));
                        if(getLevel()>1){
                            partPCs[i].execute();
                        }
                        // save
                        string s = string("./data_cups/cloud_") + to_string(getLevel()) + "_" + to_string(i)  + ".pcd" ;
                        //pcl::io::savePCDFileASCII(s,*cloud_filtered);
                        break;
                      }
                        //
                    case 2:
                        {
                      cloud_filtered = pcl::PointCloud<pcl::PointXYZ>::Ptr (new pcl::PointCloud<pcl::PointXYZ>);
                        // filtering target in x
                        pass.setInputCloud(cloud);
                        pass.setFilterFieldName("x");
                        pass.setFilterLimits(-numeric_limits<float>::max(),point_reference.x);
                        pass.filter(*cloud_filtered);

                        // filtering target in y
                        pass.setInputCloud(cloud_filtered);
                        pass.setFilterFieldName("y");
                        pass.setFilterLimits(-numeric_limits<float>::max(),point_reference.y );
                        pass.filter(*cloud_filtered);
                        // update
                        partPCs.push_back( PartPC(getLevel()-1,cloud_filtered));
                        if(getLevel()>1){
                            partPCs[i].execute();
                        }
                        // save
                        string s = string("./data_cups/cloud_") + to_string(getLevel()) + "_" + to_string(i)  + ".pcd" ;
                       // pcl::io::savePCDFileASCII(s,*cloud_filtered);
                        break;
                        }
                    case 3:
                        {
                       cloud_filtered = pcl::PointCloud<pcl::PointXYZ>::Ptr (new pcl::PointCloud<pcl::PointXYZ>);

                        // filtering target in x
                        pass.setInputCloud(cloud);
                        pass.setFilterFieldName("x");
                        pass.setFilterLimits(point_reference.x,numeric_limits<float>::max());
                        pass.filter(*cloud_filtered);

                        // filtering target in y
                        pass.setInputCloud(cloud_filtered);
                        pass.setFilterFieldName("y");
                        pass.setFilterLimits(-numeric_limits<float>::max(),point_reference.y );
                        pass.filter(*cloud_filtered);
                        // update
                        partPCs.push_back(PartPC(getLevel()-1,cloud_filtered ));
                        if(getLevel()>1){
                            partPCs[i].execute();
                        }
                        // save
                        string s = string("./data_cups/cloud_") + to_string(getLevel()) + "_" + to_string(i)  + ".pcd" ;
                        //pcl::io::savePCDFileASCII(s,*cloud_filtered);
                         break;
                        //*/
                        }
                }//switch
            }//for



                /*/ save
                pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_out (new pcl::PointCloud<pcl::PointXYZ>);
                int n = rand() % 10 + 1;
                for(int i=0;i<4;i++){
                    //getPartPCs()[i].execute();
                    cloud_out= getPartPCs()[i].getParentPC();
                    string s = string("./data_cups/cloud_") +  to_string(n) +  "_" +  to_string(i) + ".pcd" ;
                   // pcl::io::savePCDFileASCII( s.c_str(), *cloud_out); // cloud full
                    //cout<<"recursivo"<<i<<endl;
                }
                //*/


        }



};





/** Put a symbol for verification (ex: "-icp" ), a delimiter to separate the parameters(",") and the numbers of parameters
 * separeted by this delimiter. The function return a vector of strings (tokens) where each parameter is a string.
*/
vector<string> get_parameters(int argc, char **argv ,const char *symbol, const char *delimiter );


/** Open cloud in pcd. If the cannot open the file, the program finish
*/
void openCloudPCD(string filename, pcl::PointCloud<pcl::PointXYZ>::Ptr cloud );


/** Crop in cloud. Get a radius 'r' and a point reference, and get the points inside
 * the sphere centering in point reference with radius 'r'.
 *
*/
void m_crop(pcl::PointCloud<pcl::PointXYZ>::Ptr cloud, pcl::PointXYZ point, double radius,
                      pcl::PointCloud<pcl::PointXYZ>::Ptr  cloudOut);

/** Get the point NoseTip in file .lm3 from Bosphorus base
*/
pcl::PointXYZ get_noseTip_lm3(string file_path);


/** ICP pcl
*/
void icp_pcl(pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_source,
                        pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_target,
                        pcl::PointCloud<pcl::PointXYZ> &cloud_source_regist,
                        double transf_epsilon, int max_it,
                        pcl::IterativeClosestPoint<PointXYZ, PointXYZ>& icp
                        );

// soucharge
void icp_pcl(PointCloudXYZPtr cloud_source,
                        PointCloudXYZ::Ptr cloud_target,
                        PointCloudXYZ& cloud_source_regist,
                        double transf_epsilon,int max_it,int max_distance,
                        pcl::IterativeClosestPoint<PointXYZ, PointXYZ>& icp
                        );


/**
 * Niveis de quadrantes
 */
void quad_hierarquia(int level, pcl::PointCloud<pcl::PointXYZ>::Ptr cloud, pcl::PointCloud<pcl::PointXYZL>::Ptr cloud_latim );


void savePCD(const char* path,PointCloudXYZPtr cloud);

int* getIdxMinMax(std::valarray<double> array);
void print4x4Matrix (string path, const Eigen::Matrix4f &matrix);


// CLOUD PRTITIONTING
bool comparePointX(pcl::PointXYZ p1, pcl::PointXYZ p2);
bool comparePointY(pcl::PointXYZ p1, pcl::PointXYZ p2);
bool comparePointZ(pcl::PointXYZ p1, pcl::PointXYZ p2);
std::vector<PointCloudXYZPtr> cloudPartitioning(PointCloudXYZPtr cloud, int n, string field);

double get_points_RMSE(PointCloudConstPtr source, PointCloudConstPtr target,
                       PointCloudXYZPtr cloud_occlusion, PointCloudXYZPtr cloud_occlusion_removed, double dist_thr, int penality);

double z_penality(double distz , double dist);
double get_RMSE(PointCloudConstPtr m_source, PointCloudConstPtr m_target,double dist_thr);
void get_restored_occlusion(PointCloudXYZPtr cloud_source, PointCloudXYZPtr cloud_target,
                            PointCloudXYZPtr cloud_result);

void get_restored_occlusion2(PointCloudXYZPtr cloud_source, PointCloudXYZPtr cloud_target,
                            PointCloudXYZPtr cloud_result, double th);

// METRICAS
void getMetricas(PointCloudConstPtr cloud_GT, PointCloudConstPtr cloud_source_regist,
                 PointCloudConstPtr cloud_remaining,
                 int& TP, int& FN, int& FP, int& TN);



// VIZUALIZATION
PointCloudXYZRGB xyz_2_xyzrgb(PointCloudXYZPtr cloud, int R, int G, int B );
