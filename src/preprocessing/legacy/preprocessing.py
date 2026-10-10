#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time

count=0
timeSum=0
totalSample=4666
pathBase="BOSPHORUS_PCD"
pathPeople="../DATA/BASES/original/{}".format(pathBase)
pathOut = "../DATA/BASES/preprocessed/BOSPHORUS_OCCLUSIONS_NEUTRALS"
debug = 0

for person in os.listdir(pathPeople):
    if person.startswith("."): continue
    pathPerson = pathPeople + "/" + person
    for cloud in os.listdir(pathPerson):
        
        filenameSplit= cloud.split('.')[0].split('_')
        tp = filenameSplit[1]
        
        if (cloud.split('.')[1] != 'pcd'): continue
        if (tp != 'N') and (tp != 'O'): #or (filenameSplit[0]!= 'bs024')
            continue
        
        cloudIn= "{}/{}/{} ".format(pathPeople, person, cloud)
        print(cloudIn)

        # creat path if not exist (by region)
        outputFolder = "{}/{}".format(
            pathOut, person)
        if not os.path.exists(outputFolder):
            os.makedirs(outputFolder)
        cloudOut = "{}/{}".format(outputFolder, cloud)

        # outlier removal
        paramsOR = "-radius 5 -min_pts 10 -negative 0"
        outlierRemovalCmd = "pcl_outlier_removal {} {} {} ".format(cloudIn,cloudOut,paramsOR)
        
        # voxel grid
        paramsVG = "-leaf 2,2,2"
        ovoxelGridCmd = "pcl_voxel_grid {} {} {} ".format(cloudOut,cloudOut,paramsVG)
        
        start = time.time()
        # execute
        os.system(outlierRemovalCmd)
        os.system(ovoxelGridCmd)
        
        total = time.time() - start
        timeSum=timeSum+total

        if debug == 1: os.system("pcl_viewer {}".format(cloudOut))
        
        # debug
        count = count + 1
        percent = round(100 * count / totalSample, 2)
        print('{}% concluído  -- feito para {} '.format(percent, cloud))

    #     break
    # break



timeMean=timeSum/count 
print('count: {} - sum: {} - mean: {}'.format(count,timeSum,timeMean))
with open('time_preprossesing.dat', 'w') as fileoutput:
    fileoutput.write("time_mean\n")
    fileoutput.write('{}'.format(timeMean))

