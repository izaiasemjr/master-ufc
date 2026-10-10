#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar  3 23:18:24 2020

@author: izaiasjr
"""
import os
import json
import shutil



def main():

    # Get params from json
    exe = "../build/keypoints_grid"
    pathPeople = "../../../DATA/RESULTS_CROP/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/registrations_crop80"
    keypointsPath = "../../../DATA/RESULTS_REGISTRO/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/landmarks_transformed"
    pathOut = "../../../DATA/RESULTS_KEYPOINTS/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8"
    count = 0

    grids = [
            ['normal', '60', '11', '11', '6'],
            ['sparse','10','16','11','6'],
             ['sparse', '15', '11', '11', '6'],
            ['normal', '15', '11', '11', '6'],
             ['normal', '30', '11', '11', '6'],
             ['sparse', '30', '11', '11', '6']
             ]

    for grid in grids:

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

                    grid_param = "-grid {}".format(",".join(grid))

                    # creat path if not exist (by region)
                    gridlabel = '_'.join(grid)
                    outputFolder = "{}/{}/{}".format(pathOut, gridlabel, person)
                    if not os.path.exists(outputFolder):
                        os.makedirs(outputFolder)

                    output_param = "-output {}/{}".format(outputFolder, cloud)

                    command = "{} {} {} {} {} -debug 0".format(
                        exe, cloud_param, keypoints_param, grid_param,
                        output_param)

                    count = count + 1
                    percent = round(100 * count / (len(grids) * 680), 2)
                    print('{}% -->> feito para nuvem ({}) '.
                          format(percent, cloud))

                    os.system(command)
                    # print(command)
            #     break
            # break


if __name__ == "__main__":
    main()
