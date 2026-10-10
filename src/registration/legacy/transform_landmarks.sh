#!/bin/bash


pathMats="./DATA/RESULTS_REGISTRO/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/registrations/"
pathNosesIn="./DATA/BASES/original/LANDMARKS_PCD/"
pathNosesTransformed="./DATA/RESULTS_REGISTRO/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/landmarks_transformed/"


for personPath in $pathMats* ;do	
			
			m_person=${personPath##*/} 
			personPath=$personPath"/*.mat"
			for mat in $personPath ;do
							
				filename=${mat##*/} 							
				cloudNoseIn=$pathNosesIn""$m_person"/"${filename%.*}.pcd			
				cloudNoseTransformed=$pathNosesTransformed""$m_person"/"${filename%.*}.pcd			
				
				# create directory output				
				mkdir -p $pathNosesTransformed""$m_person"/"			
				

				## transform matrix to line
				matLine=""
				while read line; do
					for word in $line;do
						matLine=$matLine",$word"		
					done	
				done <$mat
				matLine=${matLine#","}
			

				exec="pcl_transform_point_cloud $cloudNoseIn $cloudNoseTransformed -matrix  $matLine "
				$exec
				
				convert="pcl_convert_pcd_ascii_binary  $cloudNoseTransformed $cloudNoseTransformed 0"				
				$convert					
				# ./mat2line.sh $mat
			
			done
	
done


