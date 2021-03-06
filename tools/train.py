import _init_paths
from net.common import *
from net.utility.file import *
from net.processing.boxes import *
from net.processing.boxes3d import *
from net.utility.draw import *

from data.data import *      #################

from net.rpn_loss_op import *
from net.rcnn_loss_op import *
from net.rpn_target_op import make_bases, make_anchors, rpn_target, anchor_filter,rpn_target_Z
from net.rcnn_target_op import rcnn_target, rcnn_target_ohem, rcnn_target_2d, rcnn_target_ohem_2d, rcnn_target_2d_z,rcnn_target_2d_z_ohem

from net.rpn_nms_op     import draw_rpn_nms, draw_rpn
from net.rcnn_nms_op    import rcnn_nms, draw_rcnn_nms, draw_rcnn,rcnn_nms_2d
from net.rpn_target_op  import draw_rpn_gt, draw_rpn_targets, draw_rpn_labels
from net.rcnn_target_op import draw_rcnn_targets, draw_rcnn_labels

import mayavi.mlab as mlab

import time
import glob
import tensorflow as tf
slim = tf.contrib.slim

from ResNet50_vgg_double_up_c import *
from tensorflow.python import debug as tf_debug
# os.environ["QT_API"] = "pyqt"

#http://3dimage.ee.tsinghua.edu.cn/cxz
# "Multi-View 3D Object Detection Network for Autonomous Driving" - Xiaozhi Chen, CVPR 2017

def load_dummy_datas(index):

    num_frames = []
    rgbs      =[]
    # lidars    =[]
    tops      =[]
    fronts    =[]
    gt_labels =[]
    gt_boxes3d=[]
    gt_boxes2d=[]
    rgbs_norm =[]
    top_images  =[]
    front_images=[]

    # pdb.set_trace()
    if num_frames==[]:
        num_frames=len(index)
        print('num_frames:%d'%num_frames)
    for n in range(num_frames):
        print('processing img:%d,%05d'%(n,int(index[n])))
        try:
            gt_label  = np.load(CFG.PATH.TRAIN.TARGET+'/gt_labels/gt_labels_%05d.npy'%int(index[n]))
        except:
            print('No target in this image')
            continue
        rgb   = cv2.imread(CFG.PATH.TRAIN.KITTI+'/image_2/%06d.png'%int(index[n]))
        # rgbs_norm0   = np.load(CFG.PATH.TRAIN.TARGET+'/image_stack_lidar/image_stack_lidar%05d .npy'%int(index[n]))
        # print(rgbs_norm0.shape)
        rgbs_norm0=(rgb-PIXEL_MEANS)/255
        # lidar = np.load(CFG.PATH.TRAIN.TARGET+'/lidar/lidar_%05d.npy'%int(index[n]))
        top   = np.load(CFG.PATH.TRAIN.TARGET+'/top_70/top_70%05d.npy'%int(index[n]))
        front = np.zeros((1,1),dtype=np.float32)

        gt_label  = np.load(CFG.PATH.TRAIN.TARGET+'/gt_labels/gt_labels_%05d.npy'%int(index[n]))
        gt_box3d = np.load(CFG.PATH.TRAIN.TARGET+'/gt_boxes3d/gt_boxes3d_%05d.npy'%int(index[n]))

        rgb_shape   = rgb.shape

        # gt_rgb   = project_to_rgb_roi  (gt_box3d, rgb_shape[1], rgb_shape[0]  )
        # keep = np.where((gt_rgb[:,1]>=-200) & (gt_rgb[:,2]>=-200) & (gt_rgb[:,3]<=(rgb_shape[1]+200)) & (gt_rgb[:,4]<=(rgb_shape[0]+200)))[0]
        # gt_label=gt_label[keep]
        # gt_box3d=gt_box3d[keep]

        top_image   = cv2.imread(CFG.PATH.TRAIN.TARGET+'/density_image_70/density_image_70%05d.png'%int(index[n]))
        gt_label  = np.load(CFG.PATH.TRAIN.TARGET+'/gt_labels/gt_labels_%05d.npy'%int(index[n]))
        gt_box3d = np.load(CFG.PATH.TRAIN.TARGET+'/gt_boxes3d/gt_boxes3d_%05d.npy'%int(index[n]))
        gt_box2d = np.load(CFG.PATH.TRAIN.TARGET+'/gt_boxes2d/gt_boxes2d_%05d.npy'%int(index[n]))
        top_image   = cv2.imread(CFG.PATH.TRAIN.TARGET+'/density_image_70/density_image_70%05d.png'%int(index[n]))

        front_image = np.zeros((1,1,3),dtype=np.float32)

        rgbs.append(rgb)
        # lidars.append(lidar)
        tops.append(top)
        fronts.append(front)
        gt_labels.append(gt_label)
        gt_boxes3d.append(gt_box3d)
        gt_boxes2d.append(gt_box2d)
        top_images.append(top_image)
        front_images.append(front_image)
        rgbs_norm.append(rgbs_norm0)

        # explore dataset:
        if 0:
            fig = mlab.figure(figure=None, bgcolor=(0,0,0), fgcolor=None, engine=None, size=(1000, 500))
            projections=box3d_to_rgb_projections(gt_box3d)
            rgb1 = draw_rgb_projections(rgb, projections, color=(255,255,255), thickness=2)
            top_image1 = draw_box3d_on_top(top_image, gt_box3d, color=(255,255,255), thickness=2)

            imshow('rgb',rgb1)
            imshow('top_image',top_image1)
            azimuth,elevation,distance,focalpoint = MM_PER_VIEW1
            mlab.view(azimuth,elevation,distance,focalpoint)
            mlab.clf(fig)
            draw_lidar(lidar, fig=fig)
            draw_gt_boxes3d(gt_box3d, fig=fig)
            mlab.show(1)
            cv2.waitKey(0)
            mlab.close()
            pass
    # pdb.set_trace()
    # rgbs=np.array(rgbs)
    ##exit(0)
    mlab.close(all=True)
    return  rgbs, tops, fronts, gt_labels, gt_boxes3d, gt_boxes2d, top_images, front_images, rgbs_norm, index#, lidars

index_list=open(CFG.PATH.TRAIN.TARGET+'/train.txt')
index = [ int(i.strip()) for i in index_list]
print ('length of index : %d'%len(index))
MM_PER_VIEW1 = 180, 70, 30, [1,1,0]
vis=CFG.TRAIN.VISUALIZATION
def run_train():
    CFG.KEEPPROBS=0.5
    # output dir, etc
    out_dir = CFG.PATH.TRAIN.OUTPUT
    makedirs(out_dir +'/tf')
    makedirs(out_dir +'/check_points')
    makedirs(out_dir +'/log')
    log = Logger(out_dir+'/log/log_%s.txt'%(time.strftime('%Y-%m-%d %H:%M:%S')),mode='a')
    
    index=np.load(CFG.PATH.TRAIN.TARGET+'/train_list.npy')
    # index_file=open(CFG.PATH.TRAIN.TARGET+'/train.txt')
    # index = [ int(i.strip()) for i in index_file]
    # index_file.close()
    index=sorted(index)
    index=np.array(index)
    num_frames = len(index)

    #lidar data -----------------
    if 1:
        ###generate anchor base 
        ratios_rgb=np.array([0.3,0.6,.75,1], dtype=np.float32)
        scales_rgb=np.array([0.5,1,2,4],   dtype=np.float32)
        bases_rgb = make_bases(
            base_size = 48,
            ratios=ratios_rgb,
            scales=scales_rgb
        )
        ratios=np.array([1.7,2.4,2.7])
        scales=np.array([1.7,2.4])
        bases=np.array([[-19.5, -8, 19.5, 8],
                        [-8, -19.5, 8, 19.5],
                        [-27.5, -11, 27.5, 11],
                        [-11, -27.5, 11, 27.5],
                        [-5, -3, 5, 3],
                        [-3, -5, 3, 5]
                        ])
        # pdb.set_trace()

        num_bases = len(bases)
        num_bases_rgb = len(bases_rgb)
        stride = 4

        out_shape=(8,3)
        rgbs, tops, fronts, gt_labels, gt_boxes3d, gt_boxes2d, top_imgs, front_imgs, rgbs_norm, image_index = load_dummy_datas(index[:3])
        # rgbs, tops, fronts, gt_labels, gt_boxes3d, top_imgs, front_imgs, rgbs_norm, image_index, lidars = load_dummy_datas()
        top_shape   = tops[0].shape
        front_shape = fronts[0].shape
        rgb_shape   = rgbs[0].shape
        top_feature_shape = ((top_shape[0]-1)//stride+1, (top_shape[1]-1)//stride+1)
        rgb_feature_shape = ((rgb_shape[0]-1)//stride+1, (rgb_shape[1]-1)//stride+1)
        # set anchor boxes
        num_class = 2 #incude background
        anchors, inside_inds =  make_anchors(bases, stride, top_shape[0:2], top_feature_shape[0:2])
        anchors_rgb, inside_inds_rgb =  make_anchors(bases_rgb, stride, rgb_shape[0:2], rgb_feature_shape[0:2])
        print ('out_shape=%s'%str(out_shape))
        print ('num_frames=%d'%num_frames)

        #-----------------------
        #check data
        if 0:
            fig = mlab.figure(figure=None, bgcolor=(0,0,0), fgcolor=None, engine=None, size=(1000, 500))
            draw_lidar(lidars[0], fig=fig)
            draw_gt_boxes3d(gt_boxes3d[0], fig=fig)
            mlab.show(1)
            cv2.waitKey(1)

    #load model ####################################################################################################
    top_anchors     = tf.placeholder(shape=[None, 4], dtype=tf.int32,   name ='anchors'    )
    top_inside_inds = tf.placeholder(shape=[None   ], dtype=tf.int32,   name ='inside_inds')

    rgb_anchors     = tf.placeholder(shape=[None, 4], dtype=tf.int32,   name ='anchors_rgb'    )
    rgb_inside_inds = tf.placeholder(shape=[None   ], dtype=tf.int32,   name ='inside_inds_rgb')

    top_images   = tf.placeholder(shape=[None, *top_shape  ], dtype=tf.float32, name='top'  )
    front_images = tf.placeholder(shape=[None, *front_shape], dtype=tf.float32, name='front')
    rgb_images   = tf.placeholder(shape=[None, None, None, 3 ], dtype=tf.float32, name='rgb'  )
    top_rois     = tf.placeholder(shape=[None, 5], dtype=tf.float32,   name ='top_rois'   ) #<todo> change to int32???
    front_rois   = tf.placeholder(shape=[None, 5], dtype=tf.float32,   name ='front_rois' )
    rgb_rois     = tf.placeholder(shape=[None, 5], dtype=tf.float32,   name ='rgb_rois'   )

    top_features, top_scores, top_probs, top_deltas, proposals, proposal_scores,deltasZ,proposals_z,inside_inds_nms = \
        top_feature_net(top_images, top_anchors, top_inside_inds, num_bases)
    # pdb.set_trace()
    front_features = front_feature_net(front_images)
    rgb_features, rgb_scores, rgb_probs, rgb_deltas  = rgb_feature_net(rgb_images, num_bases_rgb) 

    fuse_scores, fuse_probs, fuse_deltas, fuse_deltas_2d = \
        fusion_net(
            ( [top_features,     top_rois,     7,7,1./stride],
              [front_features,   front_rois,   0,0,1./stride],  #disable by 0,0
              [rgb_features,     rgb_rois,     7,7,1./stride],
              ),
            num_class, out_shape) #<todo>  add non max suppression

    #loss ########################################################################################################
    top_inds     = tf.placeholder(shape=[None   ], dtype=tf.int32,   name='top_ind'    )
    top_pos_inds = tf.placeholder(shape=[None   ], dtype=tf.int32,   name='top_pos_ind')
    top_labels   = tf.placeholder(shape=[None   ], dtype=tf.int32,   name='top_label'  )
    top_targets  = tf.placeholder(shape=[None, 4], dtype=tf.float32, name='top_target' )
    top_targets_z  = tf.placeholder(shape=[None, 2], dtype=tf.float32, name='top_target_z' )

    top_cls_loss, top_reg_loss, top_reg_loss_z= rpn_loss_z(2*top_scores, top_deltas, top_inds, top_pos_inds, top_labels, top_targets,deltasZ, top_targets_z)

    rgb_inds     = tf.placeholder(shape=[None   ], dtype=tf.int32,   name='rgb_ind'    )
    rgb_pos_inds = tf.placeholder(shape=[None   ], dtype=tf.int32,   name='rgb_pos_ind')
    rgb_labels   = tf.placeholder(shape=[None   ], dtype=tf.int32,   name='rgb_label'  )
    rgb_targets  = tf.placeholder(shape=[None, 4], dtype=tf.float32, name='rgb_target' )
    rgb_cls_loss, rgb_reg_loss = rpn_loss(2*rgb_scores, rgb_deltas, rgb_inds, rgb_pos_inds, rgb_labels, rgb_targets)


    fuse_labels  = tf.placeholder(shape=[None            ], dtype=tf.int32,   name='fuse_label' )
    fuse_targets = tf.placeholder(shape=[None, *out_shape], dtype=tf.float32, name='fuse_target')

    fuse_targets_2d = tf.placeholder(shape=[None, 4], dtype=tf.float32, name='fuse_target')

    fuse_scores_ohem=tf.stop_gradient(fuse_scores)
    fuse_deltas_ohem=tf.stop_gradient(fuse_deltas)
    fuse_labels_ohem=tf.stop_gradient(fuse_labels)
    fuse_targets_ohem=tf.stop_gradient(fuse_targets)

    # fuse_cls_loss, fuse_reg_loss = rcnn_loss(fuse_scores, fuse_deltas, fuse_labels, fuse_targets)
    rcnn_pos_inds = tf.placeholder(shape=[None   ], dtype=tf.int32,   name='top_pos_ind')
    fuse_cls_loss, fuse_reg_loss, fuse_reg_loss_2d = rcnn_loss_2d(fuse_scores, fuse_deltas, fuse_labels, fuse_targets, fuse_deltas_2d, fuse_targets_2d,rcnn_pos_inds)
    
    softmax_loss_ohem, rcnn_smooth_l1_ohem = rcnn_loss_ohem(fuse_scores_ohem, fuse_deltas_ohem, fuse_labels_ohem, fuse_targets_ohem)

    tf.summary.scalar('rpn_cls_loss', top_cls_loss)
    tf.summary.scalar('rpn_reg_loss', top_reg_loss)
    tf.summary.scalar('rpn_reg_loss_z', top_reg_loss_z)
    tf.summary.scalar('rcnn_cls_loss', fuse_cls_loss)
    tf.summary.scalar('rcnn_reg_loss', fuse_reg_loss)
    tf.summary.scalar('rcnn_reg_loss_2d', fuse_reg_loss_2d)
    tf.summary.scalar('rgb_cls_loss', rgb_cls_loss)
    tf.summary.scalar('rgb_reg_loss', rgb_reg_loss)

    #solver
    l2 = l2_regulariser(decay=CFG.TRAIN.WEIGHT_DECAY)
    tf.summary.scalar('l2', l2)
    learning_rate = tf.placeholder(tf.float32, shape=[])
    solver = tf.train.AdamOptimizer(learning_rate)
    solver_step = solver.minimize(1*top_cls_loss+1*top_reg_loss+1*fuse_cls_loss+1*fuse_reg_loss+1*fuse_reg_loss_2d+top_reg_loss_z+l2)

    max_iter = 200000
    iter_debug=1

    # start training here  #########################################################################################
    log.write('epoch     iter    speed   rate   |  top_cls_loss   reg_loss   |  fuse_cls_loss  reg_loss  |  \n')
    log.write('-------------------------------------------------------------------------------------\n')

    merged = tf.summary.merge_all()

    sess = tf.InteractiveSession()  
    train_writer = tf.summary.FileWriter( './outputs/tensorboard/R2R_3drpn_rgb_rpn',
                                      sess.graph)
    with sess.as_default():
        sess.run( tf.global_variables_initializer(), { IS_TRAIN_PHASE : True } )
        # sess = tf_debug.LocalCLIDebugWrapperSession(sess)
        # summary_writer = tf.summary.FileWriter(out_dir+'/tf', sess.graph)
        saver  = tf.train.Saver() 
        
        #Initial the network from fine-trained model
        # saver.restore(sess, './outputs/check_points/snap_R2R_030000.ckpt') 

        #Initial the network from resnet 50
        rgb_lt_res=[v for v in tf.trainable_variables() if v.name.startswith('resnet_v1_50')]#resnet_v1_50
        saver_0=tf.train.Saver(rgb_lt_res)        
        saver_0.restore(sess, './outputs/check_points/resnet_v1_50.ckpt')
        top_lt=[v for v in tf.trainable_variables() if v.name.startswith('top_base')]
        top_lt.pop(0)
        for v in top_lt:
            for v_rgb in rgb_lt_res:
                if v.name[9:]==v_rgb.name:
                    print ("assign weights:%s"%v.name)
                    v.assign(v_rgb)        

        batch_top_cls_loss =0
        batch_top_reg_loss =0
        batch_fuse_cls_loss=0
        batch_fuse_reg_loss=0
        # # rate=0.00005
        frame_range = np.arange(num_frames)
        idx=0
        frame=0
        for iter in range(max_iter):
            epoch=iter//num_frames+1
            # rate=0.001
            start_time=time.time()
            if iter%(num_frames*2)==0:
                idx=0
                frame=0
                count=0
                end_flag=0
                frame_range1 = np.random.permutation(num_frames)
                if np.all(frame_range1==frame_range):
                    raise Exception("Invalid level!", permutation)
                frame_range=frame_range1

            #load freq samples every 2*freq iterations
            freq=int(10)
            if idx%freq==0 :
                count+=idx
                if count%(2*freq)==0:
                    frame+=idx
                    frame_end=min(frame+freq,num_frames)
                    if frame_end==num_frames:
                        end_flag=1
                    # pdb.set_trace()
                    del rgbs, tops, fronts, gt_labels, gt_boxes3d, gt_boxes2d, top_imgs, front_imgs, rgbs_norm, image_index
                    rgbs, tops, fronts, gt_labels, gt_boxes3d, gt_boxes2d, top_imgs, front_imgs, rgbs_norm, image_index = load_dummy_datas(index[frame_range[frame:frame_end]])
                idx=0
            if (end_flag==1) and (idx+frame)==num_frames:
                idx=0
            print('processing image : %s'%image_index[idx])

            if (iter+1)%(CFG.TRAIN.LEARNING_RATE_DECAY_STEP)==0:
                CFG.TRAIN.LEARNING_RATE=CFG.TRAIN.LEARNING_RATE_DECAY_SCALE*CFG.TRAIN.LEARNING_RATE

            rgb_shape   = rgbs[idx].shape
            batch_top_images    = tops[idx].reshape(1,*top_shape)
            batch_front_images  = fronts[idx].reshape(1,*front_shape)
            batch_rgb_images    = rgbs_norm[idx].reshape(1,*(rgbs_norm[idx].shape))
            # batch_rgb_images    = rgbs[idx].reshape(1,*rgb_shape)

            top_img=tops[idx]
            inside_inds_filtered=anchor_filter(top_img[:,:,-1], anchors, inside_inds)
            # inside_inds_filtered_rgb=anchor_filter(batch_rgb_images[0,:,:,-1], anchors_rgb, inside_inds_rgb)
            inside_inds_filtered_rgb= inside_inds_rgb

            batch_gt_labels    = gt_labels[idx]
            if len(batch_gt_labels)==0:
                idx=idx+1
                continue

            batch_gt_boxes3d   = gt_boxes3d[idx]
            batch_gt_boxes2d   = gt_boxes2d[idx]

            # pdb.set_trace()
            batch_gt_top_boxes = box3d_to_top_box(batch_gt_boxes3d)
            batch_gt_boxesZ=get_boxes3d_z(batch_gt_boxes3d)

            #jitter ground truth
            gen_top_rois, gen_proposals_z=generate_3d_boxes_samples(batch_gt_top_boxes,batch_gt_boxesZ)
            gen_rois3D = top_z_to_box3d(gen_top_rois[:,1:5],gen_proposals_z)
            print('nums of gt targets :%d'%len(batch_gt_boxes3d))      

            ## run propsal generation ------------
            fd1={
                top_images:      batch_top_images,
                top_anchors:     anchors,
                top_inside_inds: inside_inds_filtered,

                rgb_images:      batch_rgb_images,
                rgb_anchors:     anchors_rgb,
                rgb_inside_inds: inside_inds_filtered_rgb,

                learning_rate:  CFG.TRAIN.LEARNING_RATE,
                IS_TRAIN_PHASE:  True
            }

            batch_top_probs, batch_proposals, batch_proposal_scores, batch_top_features, batch_top_proposals_z,batch_top_inside_inds_nms= sess.run([top_probs,proposals, proposal_scores, top_features,proposals_z,inside_inds_nms],fd1)            
            ## generate  train rois  ------------
            # pdb.set_trace()
            batch_top_inds, batch_top_pos_inds, batch_top_labels, batch_top_targets, batch_top_targetsZ  = \
                rpn_target_Z ( anchors, inside_inds_filtered,  batch_gt_top_boxes, batch_gt_boxesZ,batch_top_probs,batch_top_inside_inds_nms)
             
            batch_rgb_inds, batch_rgb_pos_inds, batch_rgb_labels, batch_rgb_targets  = \
                rpn_target ( anchors_rgb, inside_inds_filtered_rgb, batch_gt_labels,  batch_gt_boxes2d)

            # batch_top_rois, batch_fuse_labels, batch_fuse_targets  = \
            #      rcnn_target(  batch_proposals, batch_gt_labels, batch_gt_top_boxes, batch_gt_boxes3d )
            
            batch_top_rois, batch_fuse_labels, batch_fuse_targets, batch_fuse_targets_2d, batch_rois3d,p_inds  = \
                    rcnn_target_2d_z(  batch_proposals, batch_gt_labels, batch_gt_top_boxes, batch_gt_boxes3d,\
                     batch_gt_boxes2d, rgb_shape[1], rgb_shape[0],batch_top_proposals_z, gen_top_rois, gen_rois3D)       
            # pdb.set_trace()
            batch_rois3d_old     = project_to_roi3d    (batch_top_rois)
            batch_front_rois = project_to_front_roi(batch_rois3d  )
            batch_rgb_rois   = project_to_rgb_roi  (batch_rois3d, rgb_shape[1], rgb_shape[0])
            print('nums of rcnn batch: %d'%len(batch_rgb_rois))
            ##debug gt generation
            if vis and iter%iter_debug==0:
                top_image = top_imgs[idx]
                rgb       = rgbs[idx]

                # img_gt     = draw_rpn_gt(top_image, batch_gt_top_boxes, batch_gt_labels)
                # img_label  = draw_rpn_labels (img_gt, anchors, batch_top_inds, batch_top_labels )
                # img_target = draw_rpn_targets(top_image, anchors, batch_top_pos_inds, batch_top_targets)
                # #imshow('img_rpn_gt',img_gt)
                # imshow('img_anchor_label',img_label)
                # #imshow('img_rpn_target',img_target)

                img_gt     = draw_rpn_gt(rgb, batch_gt_boxes2d, batch_gt_labels)
                rgb_label  = draw_rpn_labels (img_gt, anchors_rgb, batch_rgb_inds, batch_rgb_labels )
                rgb_target = draw_rpn_targets(rgb, anchors_rgb, batch_rgb_pos_inds, batch_rgb_targets)
                #imshow('img_rpn_gt',img_gt)
                imshow('img_rgb_label',rgb_label)
                #imshow('img_rpn_target',img_target)

                img_label  = draw_rcnn_labels (top_image, batch_top_rois, batch_fuse_labels )
                img_target = draw_rcnn_targets(top_image, batch_top_rois, batch_fuse_labels, batch_fuse_targets)
                #imshow('img_rcnn_label',img_label)
                if vis :
                    imshow('img_rcnn_target',img_target)


                img_rgb_rois = draw_boxes(rgb, batch_rgb_rois[:,1:5], color=(255,0,255), thickness=1)
                if vis :
                    imshow('img_rgb_rois',img_rgb_rois)
                    cv2.waitKey(1)

            ## run classification and regression loss -----------
            fd2={
                **fd1,

                top_images: batch_top_images,
                front_images: batch_front_images,
                rgb_images: batch_rgb_images,

                top_rois:   batch_top_rois,
                front_rois: batch_front_rois,
                rgb_rois:   batch_rgb_rois,

                top_inds:     batch_top_inds,
                top_pos_inds: batch_top_pos_inds,
                top_labels:   batch_top_labels,
                top_targets:  batch_top_targets,
                top_targets_z: batch_top_targetsZ,

                rgb_inds:     batch_rgb_inds,
                rgb_pos_inds: batch_rgb_pos_inds,
                rgb_labels:   batch_rgb_labels,
                rgb_targets:  batch_rgb_targets,

                fuse_labels:  batch_fuse_labels,
                fuse_targets: batch_fuse_targets,

                rcnn_pos_inds: p_inds,

                fuse_targets_2d: batch_fuse_targets_2d
            }
            _, rcnn_probs, batch_top_cls_loss, batch_top_reg_loss, batch_fuse_cls_loss, batch_fuse_reg_loss, batch_fuse_reg_loss_2d,batch_top_reg_loss_z = \
               sess.run([solver_step, fuse_probs, top_cls_loss, top_reg_loss, fuse_cls_loss, fuse_reg_loss, fuse_reg_loss_2d,top_reg_loss_z],fd2)

            speed=time.time()-start_time
            log.write('%5.1f   %5d    %0.4fs   %0.6f   |   %0.5f   %0.5f   %0.5f   |   %0.5f   %0.5f  |%0.5f   \n' %\
                (epoch, iter, speed, CFG.TRAIN.LEARNING_RATE, batch_top_cls_loss, batch_top_reg_loss, batch_top_reg_loss_z , batch_fuse_cls_loss, batch_fuse_reg_loss, batch_fuse_reg_loss_2d))
            
            # debug: ------------------------------------

            if vis and iter%iter_debug==0:
                top_image = top_imgs[idx]
                rgb       = rgbs[idx]

                batch_top_probs, batch_top_scores, batch_top_deltas  = \
                    sess.run([ top_probs, top_scores, top_deltas ],fd2)

                batch_fuse_probs, batch_fuse_deltas, batch_fuse_deltas_2d = \
                    sess.run([ fuse_probs, fuse_deltas, fuse_deltas_2d ],fd2)
                # pdb.set_trace()
                #batch_fuse_deltas=0*batch_fuse_deltas #disable 3d box prediction
                probs, boxes3d, boxes2d = rcnn_nms_2d(batch_fuse_probs, batch_fuse_deltas, batch_rois3d_old, batch_fuse_deltas_2d, batch_rgb_rois[:,1:],rgb_shape, threshold=0.05)

                ## show rpn(top) nms
                img_rpn     = draw_rpn    (top_image, batch_top_probs, batch_top_deltas, anchors, inside_inds)
                # img_rpn_nms = draw_rpn_nms(top_image, batch_proposals, batch_proposal_scores)
                #imshow('img_rpn',img_rpn)
                if vis :
                    # imshow('img_rpn_nms',img_rpn_nms)
                    cv2.waitKey(1)

                ## show rcnn(fuse) nms
                img_rcnn     = draw_rcnn (top_image, batch_fuse_probs, batch_fuse_deltas, batch_top_rois, batch_rois3d,darker=1)
                img_rcnn_nms = draw_rcnn_nms(rgb, boxes3d, probs)
                if vis :
                    imshow('img_rcnn',img_rcnn)
                    imshow('img_rcnn_nms',img_rcnn_nms)
                    cv2.waitKey(0)
            if (iter)%10==0:
                summary = sess.run(merged,fd2)
                train_writer.add_summary(summary, iter)
            # save: ------------------------------------
            
            if (iter)%CFG.TRAIN.SNAPSHOT_STEP==0 and (iter!=0):
                saver.save(sess, out_dir + '/check_points/snap_R2R_%06d.ckpt'%iter)  #iter
                # saver_rgb.save(sess, out_dir + '/check_points/pretrained_Res_rgb_model%06d.ckpt'%iter)
                # saver_top.save(sess, out_dir + '/check_points/pretrained_Res_top_model%06d.ckpt'%iter)

            idx=idx+1






## main function ##########################################################################

if __name__ == '__main__':
    print( '%s: calling main function ... ' % os.path.basename(__file__))
    run_train()