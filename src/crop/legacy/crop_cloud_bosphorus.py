#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar  3 23:18:24 2020

@author: izaiasjr
"""
import os
import json
import shutil
import numpy as np


def main():
    # -cloud  registrations/bs000/bs000_N_N_0.pcd  -keypoints landmarks_transformed/bs000/bs000_N_N_0.pcd   -crop_radius   80  -output  bs000_N_N_0_test_crop.pcd -offset 0,0,0

    # Get params from json
    exe = "../build/Crop"
    path="registrations"
    # path="occlusions_removed"
    
    pathPeople = "../../DATA/RESULTS_REGISTRO/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/"+path
    pathOut = "../../DATA/RESULTS_CROP/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/"+path
    keypointsPath = "../../DATA/RESULTS_REGISTRO/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/landmarks_transformed"

    count = 0
    crop_rays = [80]
    for crop_radius in crop_rays:

        # Separete just neutral faces and aply feature extraction
        command = ""
        for person in os.listdir(pathPeople):
            pathPerson = pathPeople + "/" + person
            for cloud in os.listdir(pathPerson):
                if (cloud.split('.')[1] != 'pcd'):
                    continue

                tp = cloud.split('_')[1]
                if tp == 'N' or tp == 'O':

                    cloud_param = "-cloud {}/{}/{} ".format(
                        pathPeople, person, cloud)

                    keypoints_param = "-keypoints {}/{}/{}".format(
                        keypointsPath, person, cloud)

                    crop_param = "-crop_radius {}".format(crop_radius)

                    # creat path if not exist (by region)
                    outputFolder = "{}_crop{}/{}".format(
                        pathOut, crop_radius, person)
                    if not os.path.exists(outputFolder):
                        os.makedirs(outputFolder)

                    output_param = "-output {}/{}".format(outputFolder, cloud)

                    command = "{} {} {} {} {} -offset 0,0,0".format(
                        exe, cloud_param, keypoints_param, crop_param,
                        output_param)

                    count = count + 1
                    percent = round(100 * count / (len(crop_rays) * 680), 2)
                    print('{}% -->> feito para nuvem ({})  '.format(percent, cloud))

                    os.system(command)
                    # print(command)
            #     break
            # break


if __name__ == "__main__":
    main()