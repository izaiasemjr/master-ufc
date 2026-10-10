#!/bin/bash


## PATHS
pathRoot="../../DATA"
global_reference=$1 # exemple apram: "mask.pcd" (include ".pcd")

#directory_name="BASE_ARTIFICIAL"
directory_name="BASES/preprocessed/BOSPHORUS_OCCLUSIONS_NEUTRALS"
directory_name_output="BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS"
pathPeople=$pathRoot"/$directory_name/"

#pathGT=$pathRoot"/BASE_ARTIFICIAL/GROUND_TRUTH/"
pathGT="null"


## PARAMETERS
exec="./build/icp-cp"

# antigos params : k=2, icp: 0.0001,200
# PARAMETERS
k=" -k 2 "
field=" -field x,y,z "
icp=" -icp 0.0001,200 " # transf_epsilon, max_it
debug=" -debug 1"
occlusion_val="1"
occlusion=" -occlusion $occlusion_val"
target_special=" -target_special $global_reference " 



for j in `seq 8 8`;do
th_j=$j
th=" -th $th_j "
th_rest=" -th_rest 1.0 " 
params=$field""$k""$icp""$th""$debug""$occlusion""$target_special""$th_rest 

# put params in file txt
echo -e "$params" > readme_params.txt 
 


# cabeçalho
ref=${global_reference##*/} #file name
ref=${ref%.*} # remove extension 
pathDATA="../cp-icp_data_"$ref"_th_$th_j.csv"

echo "person type algoritmo penality TP FN FP TN RMSE_global lambda1 lambda2 time" > $pathDATA


## itreate ovver penality (o or 1) 
#for i in `seq 0 1`;do
i=1
	
	penality=$i
	
	## PATH OUTPUT
	# pathOutRegistration=$pathRoot"/RESULTS_REGISTRO/$directory_name/CP-ICP/"$ref"_th$th_j/registrations2"
	# pathOutOcclusion=$pathRoot"/RESULTS_REGISTRO/$directory_name/CP-ICP/"$ref"_th$th_j/occlusions2"
	# pathOutNoOcclusion=$pathRoot"/RESULTS_REGISTRO/$directory_name/CP-ICP/"$ref"_th$th_j/occlusions_removed2"
	# pathOutRestoredOcclusion=$pathRoot"/RESULTS_REGISTRO/$directory_name/CP-ICP/"$ref"_th$th_j/occlusions_restored_inverse2"
	# pathOutRestoredOcclusion2=$pathRoot"/RESULTS_REGISTRO/$directory_name/CP-ICP/"$ref"_th$th_j/occlusions_restored2"
	# pathOutTrainTest=$pathRoot"/RESULTS_REGISTRO/$directory_name/CP-ICP/"$ref"_th$th_j/data_train_test2"
	
	pathOutRegistration=$pathRoot"/RESULTS_REGISTRO/$directory_name_output/CP-ICP/"$ref"_th$th_j/registrations"
	pathOutOcclusion=$pathRoot"/RESULTS_REGISTRO/$directory_name_output/CP-ICP/"$ref"_th$th_j/occlusions"
	pathOutNoOcclusion=$pathRoot"/RESULTS_REGISTRO/$directory_name_output/CP-ICP/"$ref"_th$th_j/occlusions_removed"
	pathOutRestoredOcclusion=$pathRoot"/RESULTS_REGISTRO/$directory_name_output/CP-ICP/"$ref"_th$th_j/occlusions_restored_inverse"
	pathOutRestoredOcclusion2=$pathRoot"/RESULTS_REGISTRO/$directory_name_output/CP-ICP/"$ref"_th$th_j/occlusions_restored"
	pathOutTrainTest=$pathRoot"/RESULTS_REGISTRO/$directory_name_output/CP-ICP/"$ref"_th$th_j/data_train_test"
	

	for personPath in $pathPeople* ;do	
			
		# person = bs00x	 
		m_person=${personPath##*/} 
		#echo ${personPath##*/}				
		
		# list files for each person
		personPath=$personPath"/*.pcd"

		for cloud_source in $personPath ;do
			
			file=${cloud_source##*$m_person"_"}	
			shot=${file%.*}
			type=${shot%%_*}	
			
	 	
			#if [ "$shot" == "N_N_0" ]; then
				# parameters person, source, target			
				source=" -source "$shot	
				target=" -target N_N_0 "
				person=" -person "$m_person
				paths=" -path "$pathPeople	
				GT=" -GT  "$pathGT

				# paths output (registration and occlusions)					
				registrationPath=$pathOutRegistration"/"$m_person
				occlusionPath=$pathOutOcclusion"/"$m_person	
				noOcclusionPath=$pathOutNoOcclusion"/"$m_person	
				restoredOcclusion=$pathOutRestoredOcclusion"/"$m_person	
				restoredOcclusion2=$pathOutRestoredOcclusion2"/"$m_person											
				trainTest=$pathOutTrainTest"/"$m_person
				mkdir -p $registrationPath 
	
			 	if [ "$occlusion_val" == "1" ];then
					mkdir -p $occlusionPath && mkdir -p $noOcclusionPath && mkdir -p $restoredOcclusion && mkdir -p $restoredOcclusion2 && mkdir -p $trainTest
				fi	   		


				# ouputs
				file_cloud=${cloud_source##*/}	 
				outputs="-outputs "$registrationPath"/"$file_cloud,$occlusionPath"/"$file_cloud,$pathDATA,$registrationPath"/"${file_cloud%.*}.mat,$noOcclusionPath"/"$file_cloud,$restoredOcclusion"/"$file_cloud,$restoredOcclusion2"/"$file_cloud,$trainTest"/"${file_cloud%_*}
			
				
				# execution 
				$exec $paths $person $source $target $params $outputs $GT -penality $penality 
				
				echo "feito para $file_cloud"
				echo ""

			#fi

		#break	
		done

	#break
	done


done




