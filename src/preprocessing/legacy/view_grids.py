#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time

count=0
timeSum=0
totalSample=4666
pathBase="BOSPHORUS_PCD"
# pathPeople="../DATA/BASES/original/{}".format(pathBase)
pathPeople="./view_outliers"

pathOut = "view_grids"
debug = 0
cloudOutView=''

rays=['0.5','2','4']

for radius in rays:
    for person in os.listdir(pathPeople):
        if person.startswith("."): continue
        pathPerson = pathPeople + "/" + person
        for cloud in os.listdir(pathPerson):
            
            filenameSplit= cloud.split('.')[0].split('_')
            tp = filenameSplit[1]
            
            if (cloud.split('.')[1] != 'pcd'): continue
            if (tp != 'N') and (tp != 'O') or (filenameSplit[0]!= 'bs079'):
                continue
            
            cloudIn= "{}/{}/{} ".format(pathPeople, person, cloud)

            # creat path if not exist (by region)
            outputFolder = "{}/{}/{}".format(
                pathOut, radius,person)
            if not os.path.exists(outputFolder):
                os.makedirs(outputFolder)
            cloudOut = "{}/{}".format(outputFolder, cloud)
            

            # voxel grid
            paramsVG = "-leaf  {},{},{}".format(radius,radius,radius)
            ovoxelGridCmd = "pcl_voxel_grid {} {} {} ".format(cloudIn,cloudOut,paramsVG)
            os.system(ovoxelGridCmd)
            


            count = count + 1
            percent = round(100 * count / (len(rays)*totalSample), 2)
            print('{}% concluído  -- feito para {} '.format(percent, cloud))

        #     break
        # break


colors = '-fc 0,0,100 -fc 0,0,100 -fc 0,0,100'
os.system('pcl_viewer -bc 255,255,255 {}/*/bs039/*N* -multiview 1 {}'.format(pathOut,colors))
