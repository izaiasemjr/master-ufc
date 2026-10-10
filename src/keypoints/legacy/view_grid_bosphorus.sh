#!/bin/bash

exe="pcl_viewer" 

face_keyopints="../DATA/RESULTS_KEYPOINTS/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/sparse_10_16_11_6/bs000/bs000_N_N_0.pcd -ps 15 -fc 150,20,150"
face="../DATA/RESULTS_CROP/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/registrations_crop80/bs000/bs000_N_N_0.pcd  -ps 5 -fc 150,150,150"
view_grid="$exe $face $face_keyopints -bc 255,255,255"

#$view_fiducials

face_keyopints="bs000_N_N_0_9-keypoints.pcd -ps 20 -fc 150,20,150"
face="../DATA/RESULTS_CROP/BASES/BOSPHORUS_OCCLUSIONS_NEUTRALS/CP-ICP/mask_mls_th8/registrations_crop80/bs000/bs000_N_N_0.pcd  -ps 7 -fc 150,150,150"
view_fiducials="$exe $face $face_keyopints -bc 255,255,255"

$view_fiducials