#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time


count=0
timeSum=0
totalSample=4666
pathBase="BOSPHORUS_PCD"
pathPeople="../DATA/BASES/original/{}".format(pathBase)
pathOut = "view_outliers"
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

        # compute get outliers
        paramsOR = "-radius 5 -min_pts 10 -negative 0"
        outlierRemovalCmd = "pcl_outlier_removal {} {} {} ".format(cloudIn,cloudOut,paramsOR)
        os.system(outlierRemovalCmd)
        
        # compute non outliers
        cloudOutOutliers = cloudOut.split(".")[0] + "_outliers.pcd"
        paramsOR = "-radius 5 -min_pts 10 -negative 1"
        outlierRemovalCmd = "pcl_outlier_removal {} {} {} ".format(cloudIn,cloudOutOutliers,paramsOR)
        os.system(outlierRemovalCmd)
        
        # view 
        os.system("pcl_viewer {} {} -ps 3 ".format(cloudOutOutliers,cloudOut))

        count = count + 1
        percent = round(100 * count / totalSample, 2)
        print('{}% concluído  -- feito para {} '.format(percent, cloud))

    #     break
    # break


timeMean=timeSum/count 
print(timeMean  )
with open('time_preprossesing.dat', 'w') as fileoutput:
    fileoutput.write("time_mean\n")
    fileoutput.write('{}'.format(timeMean))


# view 
os.system('pcl_viewer -bc 255,255,255  {}/bs017/bs017_O_GLASSES_0_outliers.pcd {}/bs017/bs017_O_GLASSES_0.pcd -ps 5  -ps 2'.format(pathOut,pathOut))
os.system('pcl_viewer -bc 255,255,255  {}/bs032/bs032_O_EYE_0_outliers.pcd {}/bs032/bs032_O_EYE_0.pcd -ps 5  -ps 2'.format(pathOut,pathOut))
os.system('pcl_viewer -bc 255,255,255  {}/bs075/bs075_O_GLASSES_0_outliers.pcd {}/bs075/bs075_O_GLASSES_0.pcd  -ps 5  -ps 2'.format(pathOut,pathOut))
