import tensorflow as tf

from utils import contextual_similarity


def mrf_loss(y_pred_vgg, y_true_vgg, distance=contextual_similarity.Distance.DotProduct,
             nnsigma=float(1.0)):
  y_pred_vgg = tf.convert_to_tensor(y_pred_vgg, dtype=tf.float32)
  y_true_vgg = tf.convert_to_tensor(y_true_vgg, dtype=tf.float32)
  
  with tf.name_scope('cx'):
    cs_flow = contextual_similarity.create(y_true_vgg, y_pred_vgg, distance, nnsigma)
    # sum_normalize:
    height_width_axis = [1, 2]
    # To:
    cs = cs_flow.cs_NHWC
    k_max_NC = tf.reduce_max(cs, axis=height_width_axis)
    contextual_similarites = tf.reduce_mean(k_max_NC, axis=[1])
    CS_loss = -tf.log(contextual_similarites)
    CS_loss = tf.reduce_mean(CS_loss)
    return CS_loss


def random_sampling(tensor_in, n, H, W, C, indices=None, batch_size=1):
  S = H * W
  tensor_NSC = tf.reshape(tensor_in, [batch_size, S, C])
  all_indices = list(range(S))
  shuffled_indices = tf.random_shuffle(all_indices)
  indices = tf.gather(shuffled_indices, list(range(n)), axis=0) if indices is None else indices
  res = tf.gather(tensor_NSC, indices, axis=1)
  return res, indices


def random_pooling(feats, output_1d_size=100, batch_size=1):
  is_input_tensor = type(feats) is tf.Tensor
  _, H, W, C = tf.convert_to_tensor(feats[0]).shape.as_list()
  
  if is_input_tensor:
    feats = [feats]
  
  # convert all inputs to tensors
  feats = [tf.convert_to_tensor(feats_i) for feats_i in feats]
  
  _, H, W, C = feats[0].shape.as_list()
  feats_sampled_0, indices = random_sampling(feats[0], output_1d_size ** 2, H, W, C)
  res = [feats_sampled_0]
  for i in range(1, len(feats)):
    feats_sampled_i, _ = random_sampling(feats[i], -1, H, W, C, indices)
    res.append(feats_sampled_i)
  
  res = [tf.reshape(feats_sampled_i, [batch_size, output_1d_size, output_1d_size, C]) for
         feats_sampled_i in
         res]
  if is_input_tensor:
    return res[0]
  return res


def crop_quarters(feature_tensor):
  N, fH, fW, fC = feature_tensor.shape.as_list()
  quarters_list = []
  quarter_size = [N, round(fH / 2), round(fW / 2), fC]
  quarters_list.append(tf.slice(feature_tensor, [0, 0, 0, 0], quarter_size))
  quarters_list.append(tf.slice(feature_tensor, [0, round(fH / 2), 0, 0], quarter_size))
  quarters_list.append(tf.slice(feature_tensor, [0, 0, round(fW / 2), 0], quarter_size))
  quarters_list.append(tf.slice(feature_tensor, [0, round(fH / 2), round(fW / 2), 0], quarter_size))
  feature_tensor = tf.concat(quarters_list, axis=0)
  return feature_tensor


def id_mrf_reg_feat(y_pred_vgg, y_true_vgg, config):
  if config.crop_quarters is True:
    y_pred_vgg = crop_quarters(y_pred_vgg)
    y_true_vgg = crop_quarters(y_true_vgg)
  
  N, fH, fW, fC = y_pred_vgg.shape.as_list()
  if fH * fW <= config.max_sampling_1d_size ** 2:
    print(' #### Skipping pooling ....')
  else:
    print(' #### pooling %d**2 out of %dx%d' % (config.max_sampling_1d_size, fH, fW))
    y_pred_vgg, y_true_vgg = random_pooling([y_pred_vgg, y_true_vgg],
                                            output_1d_size=config.max_sampling_1d_size)
  
  return mrf_loss(y_pred_vgg, y_true_vgg, distance=config.Dist, nnsigma=config.nn_stretch_sigma)
