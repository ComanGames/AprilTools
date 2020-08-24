import numpy as np
import cv2
import time
import math

import cv2.aruco as aruco

from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 unused import

import matplotlib
import matplotlib.pyplot as plt
import numpy as np



def get_camera_matrix(wpx, hpx, wmm, fmm):
    retMat=np.zeros(shape=(3,3))
    sizePx=wmm/wpx#size of a pixel in mm
    retMat[0,0]=fmm/sizePx
    retMat[1,1]=fmm/sizePx
    retMat[0,2]=wpx/2
    retMat[1,2]=hpx/2
    retMat[2,2]=1
    return retMat

def get_random_transformation_matrix(rvec,tvec):
    rvec=(np.multiply((np.random.random_sample(rvec.shape)-(np.ones(rvec.shape)/2))*2,rvec))
    tvec=(np.multiply((np.random.random_sample(tvec.shape)-(np.ones(tvec.shape)/2))*2,tvec))
    return vectors_to_matrix(rvec,tvec)


def vectors_to_matrix(rvec, tvec):
    dest, jac=cv2.Rodrigues(rvec)
    tvec=np.transpose(tvec)
    dest=np.hstack((dest,tvec))
    dest=np.vstack((dest,np.array([0,0,0,1])))
    return dest

def get_first_index_of_nparray(theArray, theValue):
    result=np.where(theArray==theValue)
    result=result[0]
    if(len(result)==0):
        return None
    result=result[0]
    return result

'''
@brief return the 4 coordinates of the corners of a marker, in the coordinate system of the marker itself, as column vectors
'''
def get_corner_base_coordinates(markerSize):
    tempMat=np.matrix([[-markerSize/2,markerSize/2,0],[markerSize/2,markerSize/2,0],[markerSize/2,-markerSize/2,0],[-markerSize/2,-markerSize/2,0]])
    return np.transpose(tempMat)

'''
@brief given the corners of a marker as a matrix of column vectors and a 4-by-4 affinity matrix, transform the corners using the matrix and return their
transformed version as a matrix of column vectors
'''
def transform_corners_with_matrix(corners, mat):
    rows,cols=mat.shape
    ones=np.ones(shape=(1,cols))
    corners=np.vstack((corners,ones))
    tempMat=mat.dot(corners)
    tempMat=tempMat[:-1,:]
    return tempMat

def get_transformation_matrix_from_base_to_marker(rvecs, tvecs, ids, marker_matrix_pairs, target_marker_id):
    reference_marker_id=None#id (determined by the marker graphics) of the marker that is currently visible together with the target marker, and position of which wrt. base is known
    base_to_ref_matrix=None#the matrix, which transforms the coordinate system from base into the coordinate system of the reference marker

    #find some marker that has a known location wrt. base and is present in the "ids" list; that is, a marker with known position, which is on the frame together with the target_marker_id marker
    for pair in marker_matrix_pairs:
        if pair['marker_id'] in ids and pair['marker_id'] != target_marker_id:
            reference_marker_id=(pair['marker_id'])
            base_to_ref_matrix=(pair['matrix'])
            break;

    target_marker_index=get_first_index_of_nparray(ids, target_marker_id)#array index in the input arrays of the target marker
    reference_marker_index=get_first_index_of_nparray(ids, reference_marker_id)#array index in the input arrays of the reference marker

    if(reference_marker_index is None or target_marker_index is None):
        return None

    camera_to_ref_matrix=vectors_to_matrix(rvecs[reference_marker_index],tvecs[reference_marker_index])
    camera_to_base_matrix=camera_to_ref_matrix.dot(np.linalg.inv(base_to_ref_matrix))

    camera_to_target_marker_matrix=vectors_to_matrix(rvecs[target_marker_index],tvecs[target_marker_index])
    base_to_target_marker_matrix=(np.linalg.inv(camera_to_base_matrix)).dot(camera_to_target_marker_matrix)
    return base_to_target_marker_matrix


def get_transformation_matrix_from_base_to_marker_for_frame(frame_list,frame_number,marker_matrix_pairs, target_marker_id):
    return get_transformation_matrix_from_base_to_marker(frame_list[frame_number]['rvecs'],frame_list[frame_number]['tvecs'],frame_list[frame_number]['ids'], marker_matrix_pairs, target_marker_id)

def get_corners_of_marker_in_base_marker_coordinate_system(rvecs,tvecs, ids, base_marker_id, target_marker_id, markerSize):
    tempMat=get_transformation_matrix_from_base_to_marker(rvecs,tvecs,ids,base_marker_id,target_marker_id)
    if tempMat is None:
        return None
    corner_base_coordinates=get_corner_base_coordinates(markerSize)
    return transform_corners_with_matrix(corner_base_coordinates,tempMat)


'''
@brief given the base to target transformation matrix and a target marker id, iterate through all the frames; on each frame,
determine how the target marker would look on the camera (2D image), using the already-determined absolute positions of other markers on the frame;
the difference between how it would look like and how it looks adds to the reprojection error, which is then returned

'''
def get_reprojection_error(base_to_target_marker_matrix, marker_matrix_pairs, target_marker_id, camera_matrix, dist_coeffs, marker_size, frame_list, max_error):
    currentErr=0

    for frame_number in range(1,len(frame_list)):#get the sum of reprojection error for all frames
        rvecs=frame_list[frame_number]['rvecs']
        tvecs=frame_list[frame_number]['tvecs']
        corners=frame_list[frame_number]['corners']
        ids=frame_list[frame_number]['ids']

        for pair in marker_matrix_pairs:#for all the markers that have a known position wrt. base...
            if pair['marker_id'] in ids and pair['marker_id'] != target_marker_id:#..and are present on the current frame
                reference_marker_id=(pair['marker_id'])
                base_to_ref_matrix=(pair['matrix'])

                ref_marker_index =get_first_index_of_nparray(ids, reference_marker_id)
                target_marker_index=get_first_index_of_nparray(ids, target_marker_id)
                if(ref_marker_index is None or target_marker_index is None):
                    continue
                    #return None

                camera_to_ref_marker_matrix=vectors_to_matrix(rvecs[ref_marker_index],tvecs[ref_marker_index])
                camera_to_target_marker_matrix=camera_to_ref_marker_matrix.dot(np.linalg.inv(base_to_ref_matrix)).dot(base_to_target_marker_matrix)
                corners3D=get_corner_base_coordinates(marker_size)
                corners3D=transform_corners_with_matrix(corners3D,camera_to_target_marker_matrix)
                corners2DNew,jac=cv2.projectPoints(corners3D,(0,0,0),(0,0,0),camera_matrix,dist_coeffs)
                corners[target_marker_index]=np.reshape(corners[target_marker_index],(2,-1))
                corners2DNew=np.reshape(corners2DNew,(2,-1))
                currentErr=currentErr+(np.sum(np.square(corners[target_marker_index]-corners2DNew)))
                if(currentErr>max_error):
                    return currentErr
    return currentErr

'''
@brief take a list of pairs between a marker id and its position wrt. base, list of frame data (containing the positions of marker corners, transformation vectors of the
markers wrt. camera, etc.), camera matrix and the distortion coefficents of the camera; use this information to fill in the unknown positions of the markers wrt. base . 
The function iterates over all frames and for each of them calculates the best guess for the position of the markers wrt. base, based on the currently available info.
It then uses reprojection error to determine which frame gives the best guess; the newly estimated marker is added to the marker-matrix pair list, together with the
estimated transformation matrix.
'''
def update_marker_matrix_pairs(marker_matrix_pairs, valid_markers_list,frame_list,camera_matrix,distortion_coefficients):
    for marker_id in valid_markers_list:#for all the potentially valid markers
        bestMat=0
        bestErr=10000000
        currentErr=0
        t = time.time()
        processedFrames=0

        marker_position_already_known=False
        for pair in marker_matrix_pairs:#if the given marker id is already in the list of all the markers with known positions
            marker_in_pairs_id=pair['marker_id']
            if marker_id == marker_in_pairs_id:
                marker_position_already_known=True
                break;
        if marker_position_already_known:
            continue

        for i in range(len(frame_list)):
            if marker_id not in frame_list[i]['ids']:#the specified marker is not on the current frame
                continue

            transMat=get_transformation_matrix_from_base_to_marker_for_frame(frame_list,i,marker_matrix_pairs,marker_id)
            if not transMat is None:
                processedFrames=processedFrames+1
                guessMat=transMat
                for j in range(1):
                    currentErr=(get_reprojection_error(guessMat,marker_matrix_pairs,marker_id,camera_matrix,distortion_coefficients,0.1,frame_list,bestErr))
                    if currentErr<bestErr:
                        bestErr=currentErr
                        bestMat=guessMat
                    guessMat=transMat.dot(get_random_transformation_matrix(np.array([[0.1,0.1,0.1]]),np.array([[0.1,0.1,0.1]])))

        print(processedFrames)
        print(bestErr)
        print(bestMat)
        newPair={}
        newPair['marker_id']=marker_id
        newPair['matrix']=bestMat
        marker_matrix_pairs.append(newPair)
    print(time.time()-t)

def plot_markers(marker_matrix_pairs, marker_size,ax):
    for pair in marker_matrix_pairs:
        marker_matrix=pair['matrix']
        corners=get_corner_base_coordinates(marker_size)
        newCorners=transform_corners_with_matrix(corners,marker_matrix)
        ax.scatter(newCorners[0,:],newCorners[1,:],newCorners[2,:])

def prepare_2d_3d_correspondances_for_pnp_solver(frame_list,frame_number,marker_matrix_pairs,marker_size):
    frame_data=frame_list[frame_number]
    ids=frame_data['ids']
    corners=frame_data['corners']

    points2D=[]
    points3D=[]
    for i in range (len(ids)):
        #the points are stored in an odd way; sometimes, the shape is (2,4), other times (4,2,1), seemingly randomly...
        points2Dtemp=corners[i]
        points2Dtemp=np.squeeze(points2Dtemp)
        points2Dtemp=points2Dtemp.reshape((4,2))

        if(len(points2D)==0):
            points2D=points2Dtemp
        else:
            points2D=np.vstack((points2D,points2Dtemp))

        for pair in marker_matrix_pairs:
            if pair['marker_id'] == ids[i]:
                reference_marker_id=(pair['marker_id'])
                base_to_target_matrix=(pair['matrix'])
                points3Dtemp=get_corner_base_coordinates(marker_size)
                points3Dtemp=transform_corners_with_matrix(points3Dtemp,base_to_target_matrix)
                points3Dtemp=np.multiply(points3Dtemp,[[1,1,1,1],[-1,-1,-1,-1],[1,1,1,1]])#todo: check if this is correct
                if(len(points3D)==0):
                    points3D=points3Dtemp
                else:
                    points3D=np.hstack((points3D,points3Dtemp))
    return (points2D, points3D)


def matrix_to_xyz_euler(rotation_matrix):
    rm=rotation_matrix
    if rm[2,0] < 1:
        if rm[2,0] > -1:
            ty=math.asin(-rm[2,0])
            tz=math.atan2(rm[1,0],rm[0,0])
            tx=math.atan2(rm[2,1],rm[2,2])
        else:
            ty=math.pi/2
            tz=-math.atan2(-rm[1,2],rm[1,1])
            tx=0
    else:
        ty=-math.pi/2
        tz=math.atan2(-rm[1,2],rm[1,1])
        tx=0
    return np.array([tx,ty,tz])

def matrix_to_translation_vector(the_matrix):
    return the_matrix[0:-1,3]

def write_line_to_file(the_file,the_line):
    the_file.write((','.join('%0.8f'%x for x in the_line))+'\n')

def generate_tracking_line_for_frame(frame_data,frame_number,marker_matrix_pairs,marker_size,camera_matrix,distortion_coefficients):
    points2D,points3D=prepare_2d_3d_correspondances_for_pnp_solver(frame_data,frame_number,marker_matrix_pairs,marker_size)
    points3D=np.array(np.transpose(points3D))
    retval, rvecCam,tvecCam=cv2.solvePnP(points3D,points2D,camera_matrix,distortion_coefficients)
    tmat=vectors_to_matrix(np.transpose(rvecCam),np.transpose(tvecCam))

   # cor=get_corner_base_coordinates(0.095)
  #  cor=np.multiply(cor,[[1,1,1,1],[-1,-1,-1,-1],[1,1,1,1]])
    #cor=transform_corners_with_matrix(cor,tmat)
    #print(cor)
    returnVec=np.hstack((np.array(frame_number),matrix_to_xyz_euler(tmat),matrix_to_translation_vector(tmat)))
    returnVec[2]=-returnVec[2]#flip y rot axis
    returnVec[3]=-returnVec[3]#flip y rot axis
    returnVec[5]=-returnVec[5]#flip y trans axis
    returnVec[6]=-returnVec[6]#flip y trans axis

    #print(retval)
    #print(rvecCam)
    #print(tvecCam)
    print(returnVec)
    return returnVec

#print(get_camera_matrix(640,480,36,35))

#cap = cv2.VideoCapture(0)

fig = plt.figure()
#fig = plt.figure(figsize=plt.figaspect(1)*1.5) #Adjusts the aspect ratio and enlarges the figure (text does not enlarge)
ax = fig.add_subplot(111, projection='3d')
#ax = fig.gca(projection='3d')
#ax.auto_scale_xyz([0,2], [0,2], [0,2])
aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_50)
parameters =  aruco.DetectorParameters_create()
parameters.cornerRefinementMethod=aruco.CORNER_REFINE_APRILTAG
#parameters.cornerRefinementMethod=aruco.CORNER_REFINE_CONTOUR
#parameters.cornerRefinementMethod=aruco
camera_matrix=get_camera_matrix(1920,1080,36,35)
distCoeffs=np.zeros(shape=(1,4))

frameData={}
frameDataList=[]

for i in range(30):
    frameData=frameData.copy()
    #filename="L:\\personal\\tracker\\testAnimCube\\%04d.png"%(i+1)
    #filename="L:\\personal\\tracker\\testAnimDetermineAxes\\%04d.png"%(i+1)
    filename="L:\\personal\\tracker\\testAnimCrazyMotion\\%04d.png"%(i+1)
    #print(filename)
    frame = cv2.imread(filename)#cap.read()
    gray = frame#cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, rejectedImgPoints = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)
    rvecs, tvecs, _objPoints = aruco.estimatePoseSingleMarkers(corners,0.095,camera_matrix,distCoeffs)
    #newCorners=get_corners_of_marker_in_base_marker_coordinate_system(rvecs,tvecs,ids,0,2,1)
    #print(newCorners)
    frameData['corners']=corners
    frameData['ids']=ids
    frameData['rvecs']=rvecs
    frameData['tvecs']=tvecs
    frameDataList.append(frameData)
    #if not newCorners is None:
    #    ax.scatter(newCorners[0,:],newCorners[1,:],newCorners[2,:])

base_matrix_pair={}#marker id vs. the transformation matrix from base to the marker; the base can be a base marker or world
valid_markers_list=[0,1,2,3,4]
markerMatrixPairList=[]
base_matrix_pair['marker_id']=0
base_matrix_pair['matrix']=np.identity(4)
markerMatrixPairList.append(base_matrix_pair)

update_marker_matrix_pairs(markerMatrixPairList, valid_markers_list,frameDataList,camera_matrix,distCoeffs)
update_marker_matrix_pairs(markerMatrixPairList, valid_markers_list,frameDataList,camera_matrix,distCoeffs)
update_marker_matrix_pairs(markerMatrixPairList, valid_markers_list,frameDataList,camera_matrix,distCoeffs)
update_marker_matrix_pairs(markerMatrixPairList, valid_markers_list,frameDataList,camera_matrix,distCoeffs)
update_marker_matrix_pairs(markerMatrixPairList, valid_markers_list,frameDataList,camera_matrix,distCoeffs)
update_marker_matrix_pairs(markerMatrixPairList, valid_markers_list,frameDataList,camera_matrix,distCoeffs)


plot_markers(markerMatrixPairList, 0.1,ax)


filename="L:\\personal\\tracker\\testNewTracking.txt"
file=open(filename,'w')

for i in range(30):
    line=generate_tracking_line_for_frame(frameDataList,i,markerMatrixPairList,0.095,camera_matrix,distCoeffs)
    write_line_to_file(file,line)
file.close()

plt.show()

'''
print(rvecs)
print(tvecs)
theMat=(vectors_to_matrix(rvecs[0], tvecs[0]))
print(theMat)
print("kokokokodaaaaak")
corners2=get_corner_base_coordinates(1)
print(corners2)
print("klof")
print(transform_corners_with_matrix(corners2,theMat))

origin=np.transpose(np.array([[0,0,0,1],[0,0,1,1]]))
newOrigin=theMat.dot(origin)
print(newOrigin)

'''

#gray = aruco.drawDetectedMarkers(gray, corners)



cv2.imshow('frame',gray)
cv2.waitKey()

#cv2.destroyAllWindows()
