#!/bin/bash


dataReference=./masks/
exec=./CP-ICP-ONE-REFERENCE.sh



for personPath in $dataReference* ;do	
	

	m_person=${personPath##*/} 
	
	# execution
	$exec $personPath
  
done	

 

