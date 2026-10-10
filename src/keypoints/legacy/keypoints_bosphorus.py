#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar  3 23:18:24 2020

@author: izaiasjr
"""
import os
import json
import shutil

def keypoints():

    # Get params from json
    exe = "../build/keypoints"
    path='registrations_crop80'
    # path='occlusions_removed_crop80'
    pathPeople = "../../../DATA/RESULTS_CROP/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/" +path
    pathPeople = "../../../DATA/RESULTS_CROP/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/" + path
    pathOut = "../../../DATA/RESULTS_KEYPOINTS/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8"
    count = 0

    methods = [
             ['iss','10','5','0.975','0.0975','5','5'],
             ['iss','15','5','0.975','0.975','5','5'],
             ['sift_normal', '10','2', '3', '4', '0.001'],
             ['sift_normal','10','4','7','8','0.0001'],
             ]

    for method in methods:

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

                    param = "-params {}".format(",".join(method))

                    # creat path if not exist (by region)
                    label = '_'.join(method)
                    outputFolder = "{}/{}/{}".format(pathOut,label, person)
                    if not os.path.exists(outputFolder):
                        os.makedirs(outputFolder)

                    output_param = "-output {}/{}".format(outputFolder, cloud)

                    command = "{} {} {} {} -debug 0".format(
                        exe, cloud_param, param,
                        output_param)

                    count = count + 1
                    percent = round(100 * count / (len(methods) * 680), 2)
                    print('{}% - {} -->> feito para nuvem ({}) '.
                          format(percent, count,cloud))

                    os.system(command)
                    # print(command)
            #     break
            # break


if __name__ == "__main__":
    keypoints()
