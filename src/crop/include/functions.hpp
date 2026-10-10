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

/*/ C++
#include <stdlib.h> //for using system calls
#include <ios>
#include <fstream>
//*/

using namespace std;


typedef pcl::PointXYZ PointXYZ;
typedef pcl::PointCloud<PointXYZ>::Ptr PointCloudXYZPtr;
typedef pcl::PointCloud<PointXYZ> PointCloudXYZ;



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

