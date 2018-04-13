#  Dependencies
#-----------------------------------------------------------------------------
import os
import scipy.sparse as sp
import pickle
from itertools import izip
from scipy.sparse.linalg import norm as sp_norm
from scipy.fftpack import fft, ifft,rfft, fftshift, ifftshift, irfft
from math import sqrt, hypot
from numpy import ndarray, conj, NINF, empty
from numpy import zeros as np_zeros
from numpy.linalg import norm as np_norm
from warnings import warn
from numbers import Number


#import test_Tensor as T


'''-----------------------------------------------------------------------------
  Core Class
-----------------------------------------------------------------------------'''

class Tensor:
  '''
      This is a class of 3rd order sparse tensors which is designed to support
      the t-product.

      Tensor Class
        Private:
          _slices - (list of sparse matrices or 3rd order ndarray)
           a list of sparse scipy matrices which represents the frontal slices of
           the tensor, i.e. the t-th element of the list will be the matrix
           A[:,:,t]. All slices will be the same type of sparse matrix. If
           slices is passed in as an ndarray, then it must only have 3
           dimensions.
          _slice_format - (string)
           a string indicating the sparse matrix format of each of the frontal
           slices in the tensor. If _slices is an ndarray it will be set to
           'dense'
          shape - (tuple of ints)
           a tuple with the shape of the tensor. The ith element of shape
           corresponds to the dimension of the ith mode.
        Public Methods:
          save
          load
          convert_slices
          set_frontal_slice
          get_front_slice
          set_scalar
          get_scalar
          resize                SPARSE UNFINISHED
          transpose              DENSE UNTESTED
          squeeze
          twist
          t-product                    DENSE CASE UNTESTED
          scale_tensor
          find_max
          is_equal_to_tensor
          frobenius_norm               UNTESTED
          norm                         UNTESTED
          cos_distance m
          to_dense
        Overloaded Methods:
          __add__
          __sub__
          __mul__                      UNTESTED
          __neg__
          __eq__                       UNTESTED
          __ne
          __getitem__                  DENSE UNTESTED
          __setitem__                  UNWRITTEN
      Class utilization
        zeros
        normalize                      UNTESTED


    TODO: -write a reshape function
          -update the convert slices to convert to dense or to sparse
          -write random Tensor
          -write print overloading
          -add in non-zero count private element?
  '''


  def _set_ndarray_as_slices(self, slices,lateral = True, key = None):
    '''
      Helper function for setting the slices when an ndarray is passed in. A
      given shape must be passed in if the ndarray is 2-dimensional to assess
      whether it's a transverse or lateral slice.

      :Input:
        slices - (ndarray)
          the slices of the tensor to set. slices must have order at most 3.
        lateral - (optional tuple)
          a bool indicating whether to set a 2d array as a lateral slice or
          as a transverse slice. Only checked for 2d array case.
        key - (optional tuple)
          The indices or slices to index into the tensor and set the elements
          with length at most 3. If no key is passed in, it's assumed that
          the slices object must be created, and self.shape will be set.
    '''
    if len(slices.shape) == 1: #assumed to be a tubal scalar
      T = slices.shape[0]
      if key:
        if len(key) == 1:
          raise ValueError("key must be at least length 2 to identify which "
                           "tubal scalar to set\n")
        elif len(key) == 2:
          self._slices[key,:] = slices
        else:
          if isinstance(key[0],slice) or isinstance(key[1],slice):
            raise ValueError("cannot set tubal scalar over 1st or 2nd modes, "
                             "slices can only be set over 3rd mode.\n")
          self._slices[key] = slices
      else:
        self._slices = ndarray((1,1,T),buffer=slices.flatten())
        self.shape = (1,1,T)
        self._slice_format = 'dense'
    elif len(slices.shape) == 2:
      (N,T) = slices.shape
      if key:
        if len(key) == 1: #assumed to be a frontal slice
          self._slices[:,:,key] = slices
        elif len(key) == 2:
          self._slices[:,key] = slices
        elif len(key) == 3:
          self._slices[key] = slices
        else:
          raise ValueError("key must be at most length 3, key is length {"
                           "}\n".format(len(key)))
      else:
        if lateral:
          self._slices = ndarray((N,1,T),buffer=slices.flatten())
          self.shape = (N,1,T)
          self._slice_format = 'dense'
        else:
          self._slices = ndarray((1,N,T),buffer=slices.flatten())
          self.shape = (1,N,T)
          self._slice_format = 'dense'
    else:
      if key:
        self._slices[key] = slices
      else:
        self._slices = slices
        self.shape = slices.shape
        self._slice_format = 'dense'



  def __init__(self, slices = None, set_lateral = True):

    if slices is not None:
      #if string passed in, assumed to be a file path
      if isinstance(slices,str):
        self.load(slices)
      elif isinstance(slices,ndarray):
        #check order of tensor
        if len(slices.shape) > 3:
          raise ValueError("ndarray must be at most order 3, slices passed in "
                           "has order {}\n".format(len(slices.shape)))
        else:
          self._set_ndarray_as_slices(slices,lateral=set_lateral)
      else:
        #check for valid slice array
        slice_shape = slices[0].shape
        slice_format = slices[0].getformat()
        for t,slice in enumerate(slices[1:],1):
          if slice.shape != slice_shape:
            raise ValueError("slices must all have the same shape, slice {} "
                             "has shape {}, but slice 0 has shape {}\n".
                             format(t,slice.shape,slice_shape))
          if slice.getformat() != slice_format:
            warn("slice format {} is different from first slice, "
                              "coverting to format {},\n this may make "
                              "initialization slow. pass in list of same type "
                              "sparse matrix for \nfaster "
                              "initialization\n".
                              format(slice.getformat(),slice_format),
                          RuntimeWarning)
            slices[t] = slice.asformat(slice_format)

        self._slices = slices
        self.shape = (slice_shape[0],slice_shape[1],len(slices))
        self._slice_format = slice_format
    else:
      self._slices = []
      self.shape = (0, 0, 0)
      self._slice_format = None

  def __mul__(self, other):
    if isinstance(other, Tensor):
      return self.t_product(other)
    elif isinstance(other, Number):
      return self.scale_tensor(other)
    else:
      raise TypeError("{} is not a subclass of Number, or a Tensor instance,\n "
                      "parameter is of type {}\n".format(other,type(other)))

  def _add_sub_helper(self,other, add):
    if isinstance(other, Tensor):
      # check dimensions
      if self.shape != other.shape:
        raise ValueError("invalid shape, input tensor must be of shape {}, \n"
                         "input tensor is of shape {}.\n".format(self.shape,
                                                                 other.shape))
      else:
        if add:
          return Tensor(
            map(lambda (x, y): x + y, zip(self._slices, other._slices)))
        else:
          return Tensor(
            map(lambda (x, y): x - y, zip(self._slices, other._slices)))
    else:
      raise TypeError("input {} passed in is not an instance of a Tensor, "
                      "parameter passed in is of type {}".
                      format(other, type(other)))

  def __add__(self, other):
    return self._add_sub_helper(other,add =True)
  def __sub__(self,other):
    return self._add_sub_helper(other,add =False)

  def __neg__(self):
    return self.scale_tensor(-1)

  def __eq__(self, other):
    return self.is_equal_to_tensor(other)

  def __ne__(self,other):
    return not self.__eq__(other)

  def __getitem__(self, key):
    if self._slice_format == 'dense':
      if isinstance(key,slice):
        new_slices = self._slices[:, :, key]
      elif isinstance(key,int):
        return self._slices[:,:,key]
      elif len(key) == 2:
        if isinstance(key[1],int):
          return self._slices[:,key[0],key[1]]
        elif isinstance(key[0],int):
          return Tensor(self._slices[:,key],set_lateral=False)
        else:
          new_slices = self._slices[:,key]
      elif len(key) == 3:
        new_slices = self._slices[key]
        if isinstance(new_slices,Number) or isinstance(key[2],int):
          return new_slices
        elif isinstance(key[0],int):
          return Tensor(new_slices,set_lateral=False)
      else:
        raise(ValueError("invalid amount of indices/slices, {} found, must add "
                         "at most 3 indices and/or slices.".format(len(key))))
      return Tensor(new_slices)
    else:
      if isinstance(key,slice):
        return Tensor(self._slices[key])
      elif isinstance(key,int):
        return self._slices[key]
      elif len(key) == 2:
        if isinstance(key[1],slice):
          return Tensor(map(lambda x: x[:,key[0]],self._slices[key[1]]))
        else:
          return self._slices[key[1]][:,key[0]]
      elif len(key) == 3:
        if isinstance(key[2],slice):
          return Tensor(map(lambda x: x[key[0],key[1]],self._slices[key[2]]))
        else:
          new_slices = self._slices[key[2]][key[0],key[1]]
          if isinstance(new_slices,Number):
            return new_slices
          else:
            if isinstance(key[2],int):
              return new_slices
            else:
              return Tensor(new_slices)
      else:
        raise(ValueError("invalid amount of indices/slices, {} found, must add "
                         "at most 3 indices and/or slices.".format(len(key))))

  def _check_slices_are_sparse(slices):
    for slice in slices:
      if not sp.issparse(slice):
        return False
    return True

  def __setitem__(self, key, value):
    if self._slice_format == "dense":
      if isinstance(value,ndarray):
        if len(value.shape) == 2 and isinstance(key[0],int):
          self._set_ndarray_as_slices(value,lateral=False,key=key)
        else:
          self._set_ndarray_as_slices(value,key=key)
      elif isinstance(value,Number):
        self._slices[key] = value
      elif _check_slices_are_sparse(value):
        pass
      else:
        raise TypeError("setting value must be either ")


  def save(self, file_name):
    '''
      This function takes in a file name and uses the pickle module to save \
    the Tensor instance.

    :Input:
      file_name - (string)
        The name of the file to save the tensor.
    '''
    with open(file_name,'w') as handle:
      pickle.dump([self._slices,self._slice_format,self.shape],handle)

  def load(self,file_name, make_new = False):
    '''
      This function takes in a file name and loads in into the current tensor \
    instance, if the make_new flag is true it will return a new instance of a \
    tensor.

    :Input:
      file_name - (string)
        The name of the file to load the tensor from.
      make_new - (bool)
        Optional bool which indicates whether or not to create a new instance of
        a tensor, or just copy it into the current instance.
    '''
    with open(file_name,'r') as handle:
      private_elements = pickle.load(handle)

    if make_new:
      return Tensor(private_elements[0])
    else:
      self._slices = private_elements[0]
      self._slice_format = private_elements[1]
      self.shape = private_elements[2]


  def convert_slices(self,format):
    '''
      This function will convert all of the slices to a desired sparse matrix \
    format, this derives its functionality from the scipy.sparse._.asformat \
    function. To convert to a dense tensor, use todense().

    :Input:
      format- (string)
        string that specifies the possible formats, valid formats are the \
        supported formats of scipy sparse matrices. see scipy reference for \
        most up to date supported formats.
    :References:
      https://docs.scipy.org/doc/scipy/reference/sparse.html
    '''
    if self._slice_format == "dense":
      raise AttributeError("this function is for sparse tensors\n")
    else:
      for t, slice in enumerate(self._slices):
        self._slices[t] = slice.asformat(format)
      self._slice_format = format

  def resize(self,shape,order = 'C'):
    '''
      This function takes in a 3 tuple and resizes the tensor according to \
    the dimension of the values passed into the tuple. The method will \
    default to row major order (C like) but may be done in col major order \
    (Fortran like).

    :Input:
      shape - (tuple or list of postive ints)
        a tuple or list with at most length 3 which has the appropriate shapes.
      order - (optional character)
        a character indicating whether or not to use column or row major \
        formatting for the reshape.
    '''
    if not isinstance(shape,list) and not isinstance(shape,tuple):
      raise TypeError('shape is not a valid list or tuple, shape is of type {'
                      '}'.format(type(shape)))
    if len(shape) > 3:
      raise ValueError('shape must be at most length 3, shape is of length {'
                       '}'.format(len(shape)))
    prod = lambda list: reduce(lambda x,y: x*y,list)
    if prod(shape) != prod(self._shape):
      raise ValueError("cannot reshape Tensor with {} entries into shape {}".
                       format(prod(self._shape),shape))

    if self._slice_format == 'dense':
      self._slices.reshape(shape,order)
      self._shape = shape
    else:
      raise NotImplementedError("resize needs to have the sparse case finished")

  def get_frontal_slice(self,t):
    '''
    returns the t-th frontal slice. Paired with set_slice().

    Input:
      t - (int)
        index of the slice to return
    Returns:
      slice - (sparse scipy matrix or ndarray)
        the t-th slice
    '''
    if self._slice_format == 'dense':
      return self._slices[:,:,t]
    else:
      return self._slices[t]


  def set_frontal_slice(self, ts, frontal_slices):
    '''
      Replaces the t-th frontal slice. Paired with get_slice().

    :Input:
      ts - (int or slice)
        index or slice object of the slices to replace. t must be in range of \
        the number of frontal slices. Use a constructor to create larger \
        Tensors.
      frontal_slice - (sparse scipy matrix)
        the new t-th slice

    TODO:
      Update to match scipy.sparse and ndarray setting interface.
    '''

    #check for valid inputs
    if isinstance(ts,int) or isinstance(ts,slice):
      self._set_frontal_slice_validator(ts,frontal_slices)
    else:
      raise(TypeError("ts are not an integer or slice, ts are of type {"
                      "}".format(type(ts))))

    self._slices[ts] = frontal_slices


  def _set_frontal_slice_validator(self,t,frontal_slice):
    '''
      This function is a helper function for determining if the inputs are \
    valid in the set_frontal_slice function. t is either ts, or an element in \
    the slice object, frontal slice is one of the matrices passed into \
    set_frontal_slice. This is separated from the formatter as the errors \
    are raised here.
    '''
    if isinstance(t,int):

      # check for valid index
      if abs(t) > self.shape[2]:
        raise ValueError("out of bounds, 3rd mode index must be less than {} "
                         "or greater than -{}".format(self.shape[2],
                                                      self.shape[2]))

      # check for correct type
      n = self.shape[0]
      m = self.shape[1]
      if not sp.issparse(frontal_slice) and not isinstance(frontal_slice,ndarray):
        raise TypeError("slice is not a scipy sparse matrix or ndarray, "
                        "slice passed in is of type {}\n".format(type(frontal_slice)))
      if frontal_slice.shape != (n, m):
        raise ValueError("slice shape is invalid, slice must be of "
                         "shape ({},"
                         "{}), slice passed in is of shape {}\n", n, m,
                         frontal_slice.shape)

  def _set_frontal_slice_formatter(self,frontal_slice):
    '''
      This function is a helper function for set_frontal_slice. It will convert\
    the slice to the current tensor slice_format. Warnings are raised if the \
    format is the not the same.

    TODO:
      may be good to only raise an error once so it doesn't burden the \
      user's stderr for large T.
    '''
    if frontal_slice.getformat() != self._slice_format:
      warn("converting frontal slice to format {}\n".
           format(self._slice_format), UserWarning)

  def set_scalar(self,k,j,i,scalar):
    '''
      This function sets i,j,k element of the tensor to be the value passed \
    as the scalar variable.Note that because COO matrices don't support \
    assignment, the tensor must be converted. paired with the get_scalar \
    function.

    :Input:
      i - (integer)
        The mode 1 index to insert the scalar
      j - (integer)
        The mode 2 index to insert the scalar
      k - (integer)
       The mode 3 index to insert the scalar
      scalar - (scalar type)
        The value to be inserted into the tensor, will be cast to the type \
        of whatever type of matrix the slices are comprised of.

    TODO:
     -expand the tensor when the use passes an index out of range of the \
      current
    '''

    if not isinstance(scalar,Number):
      raise TypeError("scalar must be a subclass of Number, scalar passed "
                      "in is of type{}\n".format(type(scalar)))
    #check for bounds
    if abs(i) > self.shape[0]:
      raise ValueError("i index out of bounds, must be in the domain [-{},"
                       "{}]".format(self.shape[0],self.shape[0]))
    if abs(j) > self.shape[1]:
      raise ValueError("j index out of bounds, must be in the domain [-{},"
                       "{}]".format(self.shape[1],self.shape[1]))
    if abs(k) > self.shape[2]:
      raise ValueError("k index out of bounds, must be in the domain [-{},"
                       "{}]".format(self.shape[2],self.shape[2]))

    #can't assign elements to a coo matrix
    if self._slices[0].format == 'coo':
      warn("Tensor slices are of type coo, which don't support index "
                    "assignment, Tensor slices are being converted to dok.\n",
                    RuntimeWarning)
      self.convert_slices('dok')

    self._slices[k][i,j] = scalar

  def get_scalar(self,k,j,i):
    '''
      This function gets the i,j,k element of the tensor. paired with the \
    set_scalar function.

    :Input:
      i - (integer)
        The mode 1 index to insert the scalar
      j - (integer)
        The mode 2 index to insert the scalar
      k - (integer)
       The mode 3 index to insert the scalar
    :Returns:
      A[i,j,k] - (scalar number)
        returns the value at the i,j element of the kth frontal slice.
    '''

    #check bounds of i,j,k
    if abs(i) > self.shape[0]:
      raise ValueError("i index out of bounds, must be in the domain [-{},"
                       "{}]".format(self.shape[0],self.shape[0]))
    if abs(j) > self.shape[1]:
      raise ValueError("j index out of bounds, must be in the domain [-{},"
                       "{}]".format(self.shape[1],self.shape[1]))
    if abs(k) > self.shape[2]:
      raise ValueError("k index out of bounds, must be in the domain [-{},"
                       "{}]".format(self.shape[2],self.shape[2]))

    if self._slices[0].format == 'coo':
      warn("{}th slice is COO format, converting to dok to read value, "
           "please consider converting slices if multiple reads are needed."
           "\n".format(k),RuntimeWarning)
      return self._slices[k].asformat('dok')[i,j]
    else:
      return self._slices[k][i,j]

  def transpose(self, inPlace = False):
    '''
      Creates a new instance a tensor class such that the frontal slices \
    are transposed, and the 2nd through nth slices are flipped. Has the \
    option of returning a new instance, or in place.

    :Input:
      InPlace - (optional bool)
        A boolean indicating whether or not to alter the current tensor, \
        or produce a new one.
    :Returns:
      Tensor Instance
        if InPlace is false, then this function returns a new tensor \
        instance.

    TODO:
      In the dense case, need to find out when np.reshape will create a \
      copy of the data under the hood.
    '''

    (N, M, T) = self.shape
    if self._slice_format == "dense":
      if inPlace and N == M:
        #transpose the 0th slice first
        for i in xrange(N):
          for j in xrange(i):
            temp_val = self._slices[i,j,0]
            self._slices[i,j,0] = self._slices[j,i,0]
            self._slices[j,i,0] = temp_val


        for t in xrange(1,(T-1)/2 + 1):
          # handle off diagonals
          for i in xrange(N):
            for j in xrange(i):
              temp_val = self._slices[i,j,t]
              self._slices[i,j,t] = self.self._slices[j,i,-t%T]
              self._slices[j,i,-t%T] = temp_val

              temp_val = self._slices[j,i,t]
              self._slices[j,i, t] = self.self._slices[i, j, -t % T]
              self._slices[i, j, -t % T] = temp_val

          #handle diagonals
          for i in xrange(N):
            temp_val = self._slices[i,i,t]
            self._slices[i,i,T] = self._slices[i,i,-t%T]
            self._slices[i,i,-t%T] = temp_val

        #handle middle slice if one exists
        if (T-1)% 2 != 0:
          for i in xrange(N):
            for j in xrange(i):
              temp_val = self._slices[i,j,(T - 1)/2 + 1]
              self._slices[i, j, (T - 1) / 2 + 1] = \
                self._slices[j,i,(T - 1)/2 + 1]
              self._slices[j,i,(T-1)/2 + 1] = temp_val
      else:
        new_slices = ndarray((M,N,T))
        #handle the off diagonals
        for t in xrange(T):
          for i in xrange(N):
            for j in xrange(M):
              new_slices[j,i,t] = self._slices[i,j,- t %T]

        if inPlace:
          self._slices = new_slices
          self.shape = (M,N,T)
        else:
          return Tensor(new_slices)
    else:
      if inPlace:
        first_slice = self._slices[0].T
        self._slices = map(lambda x: x.T, self._slices[:0:-1])
        self._slices.insert(0,first_slice)
        self.shape = (self.shape[1],self.shape[0],self.shape[2])
      else:
        new_slices = map(lambda x: x.T, self._slices[:0:-1])
        new_slices.insert(0,self._slices[0].T)
        return Tensor(new_slices)

  def squeeze(self, X = None):
    '''
      This function takes in either an n x m matrix and will return a \
    (n x 1 x m) Tensor. This corresponds to thinking of the matrix as a \
    frontal slice, and having the function return it as a lateral slice. \
    Note that if no matrix is passed in, then this function will apply the \
    squeeze function to each one of the frontal slices of the current \
    instance of the tensor. Note that this function is paired with the \
    twist function as an inverse i.e. \
                        X = twist(squeeze(X)) \
    It should be noted that X will be a dok sparse matrix after the \
    function calls.

    :Input:
      X - (optional n x m sparse matrix or ndarray)
        A sparse matrix or ndarrayto be squeezed. Note if none is passed in, \
        then each frontal slice in self._slices will be squeezed and the \
        instance of the Tensor calling this function will be altered. \
    :Returns:
      Z - (n x 1 x m Tensor)
        A tensor corresponding to a single lateral slice. Doesn't return \
        anything if no X is passed in.
    '''

    if X is not None:
      if sp.issparse(X):
        n = X.shape[0]
        m = X.shape[1]

        if X.format == 'coo':
          X = X.asformat('dok')
        slices = []
        for i in range(m):
          slices.append(X[:,i])
        return Tensor(slices)
      elif isinstance(X,ndarray):
        if len(X.shape) != 2:
          raise ValueError("X passed in is not an order 2 ndarray, create an "
                           "instance of a tensor and call this method on that "
                           "class instance for a 3rd order ndarray.\n")
        else:
          (n,m) = X.shape
          return Tensor(X.reshape((n,1,m)))
      else:
        raise TypeError("X passed in not a sparse matrix, X is of type {"
                        "}\n".format(type(X)))
    else:

      #check format
      if self._slice_format == 'dense':
        (N,M,T) = self.shape
        new_slices = ndarray((N,T,M))
        for t in xrange(T):
          new_slices[:,t,:] = self._slices[:,:,t]
        self._slices = new_slices
        self.shape = (N,T,M)
      else:
        if self._slice_format == 'coo':
          warn("internally converting from coo to dok format, " \
                              "may degrade performance\n",RuntimeWarning)
          self.convert_slices('dok')

        #build new slices
        new_slices = []
        (n,m,T) = self.shape
        for i in range(m):
          new_slices.append(sp.random(n,T,density=0,format='dok'))

        #populate them
        for (t,slice) in enumerate(self._slices):
          if self._slice_format == 'dok':
            for ((i,j),val) in slice.iteritems():
              new_slices[j][i,t] = val
          else:
            if self._slice_format != 'coo':
              slice = slice.tocoo()
            for (i,j,val) in izip(slice.row,slice.col,slice.data):
              new_slices[j][i,t] = val

        self._slices = new_slices
        self.shape = (n,T,m)
        self._slice_format = 'dok'

  def twist(self, X = None):
    '''
      This function takes in an optional n x 1 x m tensor X and returns a \
    sparse n x m matrix corresponding to rotating the lateral slice to a \
    frontal slice. If no tensor is passed in, the algorithm is run on each \
    of frontal slices of the tensor this routine is being called on. Note \
    that this is the inverse function of the squeeze function, i.e. \
                        X = squeeze(twist(X))

    :Input:
      X - (optional n x 1 x m Tensor)
        This is a lateral slice to be converted to a matrix. Note that \
        if no tensor is passed in, then the routine is run on each of \
        the frontal slices of the current instance of the Tensor the \
        function is called on.
    :Returns:
       Z - (sparse dok matrix or ndarray)
         a matrix corresponding to the lateral slice. The type is determined \
         by whether the input tensor is dense or sparse.
    '''

    if X is not None:
      if not isinstance(X,Tensor):
        raise TypeError("X is not a member of the Tensor class, X is of type "
                        "{}".format(type(X)))
      elif X.shape[1] != 1:
        raise ValueError("X is not a lateral slice as the mode-2 dimension is {}"
                         " not 1,\n if you wish to twist this tensor, "
                         "call twist() on that instance".format(X.shape[1]))
      else:
        if X._slice_format == 'dense':
          Z = ndarray((X.shape[0],X.shape[2]))
          for i in xrange(X.shape[0]):
            for j in xrange(X.shape[2]):
              Z[i,j] = X._slices[i, 0, j]
          return Z
        else:
          Z = sp.random(X.shape[0],X.shape[2],format='dok',density=0)
          for t in range(X.shape[2]):

            slice = X._slices[t]
            if X._slice_format == 'dok':
              for ((i,_),v) in slice.iteritems():
                Z[i,t] = v
            else:
              if X._slice_format != 'coo':
                slice = slice.tocoo()
              for (i,_,v) in izip(slice.row,slice.col,slice.data):
                Z[i,t] = v
          return Z
    else:
      if self._slice_format == 'dense':
        new_slices = ndarray((self.shape[0],self.shape[2],self.shape[1]))
        for i in xrange(self.shape[0]):
          for j in xrange(self.shape[1]):
            for t in xrange(self.shape[2]):
              new_slices[i,t,j] = self._slices[i,j,t]
      else:
        new_slices = []
        for j in xrange(self.shape[1]):
          new_slices.append(sp.random(self.shape[0],self.shape[2],
                                      density=0, format='dok'))

        for t in xrange(self.shape[2]):
          if self._slice_format == 'dok':
            for ((i,j), v) in self._slices[t].iteritems():
              new_slices[j][i,t] = v
          else:
            slice = self._slices[t]
            if self._slice_format != 'coo':
              slice = slice.tocoo()
            for (i,j,v) in izip(slice.row,slice.col,slice.data):
              new_slices[j][i,t] = v

        #convert slices back to original format
        if self._slice_format != 'dok':
          new_slices = map(lambda x:x.asformat(self._slice_format),new_slices)

      self._slices = new_slices
      self._shape = (self.shape[0],self.shape[2],self.shape[1])

  def to_transverse(self):
    pass


  def t_product(self,B,transpose = False):
    '''
      This function takes in another tensor instance and computes the \
    t-product of the two through the block circulant definition of the \
    operation.

    :Input:
      B - (Tensor Instance)
        the mode-2 and mode -3 dimensions of the current instance of a \
        tensor must equal the mode 1 and mode 3 dimensions of B.
      transpose - (optional bool)
        a boolean indicating whether or not to transpose the tensor being \
        called upon before applying the t-product.
    :Returns:
      (Tensor Instance)
      Returns a new Tensor which represents the t-product of the current \
      Tensor and B.

    TODO:
      Can use a complex multiplication formula which may be a little less \
      numerically stable, but will improve complex matrix matrix \
      multiplication constants.
    '''

    if isinstance(B, Tensor):
      (N, M, T) = self.shape
      (M2, L, T2) = B.shape

      #check dimensions of B
      if transpose:
        if N != M2 or T != T2:
          raise ValueError("input Tensor B invalid shape {},\n mode 1 "
                           "dimension and mode 3 dimension must be equal to {} "
                           "and {} respectively"
                           "".format(B.shape, N, T))
      else:
        if M != M2 or T != T2:
          raise ValueError("input Tensor B invalid shape {},\n mode 1 "
                           "dimension and mode 3 dimension must be equal to {} "
                           "and {} respectively"
                           "".format(B.shape,M, T))

      if self._slice_format == 'dense':
        if self._slices.dtype.name == 'complex128':
          new_slices = fft(self._slices)
          B_slices = fft(B._slices)

          for t in range(T):
            new_slices[:,:,t] = np.dot(new_slices[:,:,t],B_slices[:,:,t])
          ifft(new_slices,overwrite_x=True)
        else:
          new_slices = np.empty((N,L,T),dtype ='complex128')
          A_slices = rfft(self._slices)
          B_slices = rfft(B._slices)

          #handle the first slice
          for i in xrange(N):
            for j in xrange(L):
              new_slices[i,j,0] = A_slices[i,0,0]*B_slices[0,j,0]
              for k in xrange(1,M):
                new_slices[i,j,0] += A_slices[i,k,0]*B_slices[k,j,0]

          if T % 2 == 0:
            #handle the last slice
            for i in xrange(N):
              for j in xrange(L):
                new_slices[i, j, -1] = A_slices[i, 0, -1] * B_slices[0, j, -1]
                for k in xrange(1, M):
                  new_slices[i, j, -1] +=\
                    A_slices[i, k, -1] * B_slices[k, j,-1]

            end_T = (T - 1) / 2 + 1
          else:
            end_T = T / 2 + 1

          for t in xrange(1, end_T):
            for i in xrange(N):
              for j in xrange(L):
                real = A_slices[i,0,t]*B_slices[0,j, t] - \
                       A_slices[i,0,t+1]*B_slices[0,j,t+1]
                imaginary = A_slices[i,0,t+1]*B_slices[0,j,t] + \
                            A_slices[i,0,t]*B_slices[0,j,t+1]
                new_slices[i,j,t] = complex(real,imaginary)
                new_slices[i,j,t+T/2] = complex(real,-imaginary)
                for k in xrange(1,M):
                  real = A_slices[i, k, t] * B_slices[k, j, t] - \
                         A_slices[i, k, t + 1] * B_slices[k, j, t + 1]
                  imaginary = A_slices[i, k, t + 1] * B_slices[k, j, t] +\
                              A_slices[i, k, t] * B_slices[k, j, t + 1]
                  new_slices[i, j, t] += complex(real,imaginary)
                  new_slices[i, j, t + T/2] += complex(real,-imaginary)

      else:
        new_slices = []
        for i in xrange(T):
          if transpose:
            new_slice = sp.random(M, L, density=0)
          else:
            new_slice = sp.random(N,L,density=0)
          for j in xrange(T):
            if transpose:
              new_slice += self._slices[(j + (T - i))%T].T * B._slices[j]
            else:
              new_slice += self._slices[(i + (T - j))%T] * B._slices[j]
          new_slices.append(new_slice)

      return Tensor(new_slices)
    else:
      raise TypeError("B must be a Tensor instance, input is of type {"
                      "}".format(type(B)))

  def scale_tensor(self,scalar, inPlace = False):
    '''
      This function takes in a scalar value and either returns a Tensor scaled \
    by a scalar in the field or scales the tensor in question in place and \
    returns nothing.

    :Input:
      scalar - (subclass of Number)
        must be a scalar value of a field, will be applied to each of the \
        tensor slices.
      inPlace - (optional bool)
        a bool indicating whether or not the tensor this function is called \
        on should be scaled, or whether it should return a new tensor.
    '''

    if not isinstance(scalar, Number):
      raise TypeError("{} is not a subclass of a Number, value passed in is "
                      "of type {}\n".format(scalar,type(scalar)))
    else:
      if inPlace:
        if self._slice_format == 'dense':
          for i in xrange(self.shape[0]):
            for j in xrange(self.shape[1]):
              for k in xrange(self.shape[2]):
                self._slices[i,j,k] *= scalar
        else:
          self._slices = map(lambda x: scalar *x, self._slices)
      else:
        if self._slice_format == 'dense':
          return Tensor(self._slices * scalar)
        else:
          return Tensor(map(lambda x: scalar *x, self._slices))

  def frobenius_norm(self):
    '''
      Returns the Frobenius norm of the tensor. Computed using scipy's norm \
    function for numerical stability.
    '''
    if self._slice_format == 'dense':
      return sqrt(reduce(lambda x,y: x + y**2,self._slices.flat,0))
    else:
      return np_norm(map(lambda x: sp_norm(x,ord='fro'),self._slices))

  def norm(self):
    '''
      This function returns the norm (defined with the t product) of the \
    tensor called upon. Method is computed in a manner rebust to \
    over/underflow by scaling by the largest element of the tensor.

    :Returns:
      norm - (float)
        a float indicating the size of the tensor.
    '''
    norm = 0.0
    if all(map(lambda x: x.nnz == 0,self._slices)):
      return norm
    else:
      T = self.shape[2]

      #compute frobenius norm of \langle X, X \rangle slice wise
      for i in xrange(T):
        slice = self._slices[(T - i) % T].T * self._slices[0]
        for t in xrange(1,T):
          slice += self._slices[(t + (T - i)) % T].T * self._slices[t]

        norm += sp_norm(slice,ord = 'fro')**2

      return sqrt(norm)/self.frobenius_norm()
  def tubal_angle(self,B):
    '''
      This function returns the tubal angle of the current instance of a \
    tensor with another tensor B passed in. This is defined using the inner \
    product defined by the t-product.

    :Returns:
      cos_distance - (float)
        the cosine distance between the current tensor and the tensor passed in.
    '''
    raise NotImplementedError('finish tubal_angle function')

  def find_max(self):
    '''
      This function returns the largest element of the tensor.
    '''
    if self._slice_format == 'dense':
      return self._slices.max()
    else:
      if self._slice_format == 'dok':
        max_val = NINF
        (N,M,T) = self.shape
        for t in xrange(T):
          for val in self._slices[t].itervalues():
            if val > max_val:
              max_val = val

        return max_val
      else:
        if self._slice_format in ['dia','lil']:
          reducing_func = lambda x,y: max(x,y.tocoo().max())
          initial_val = (self._slices[0].tocoo()).max()
          return reduce(reducing_func, self._slices[1:], initial_val)
        else:
          return max(map(lambda x:x.max(),self._slices))


  def zero_out(self,threshold):
    '''
      This function iterates through the non-zeros of the tensor and zeros \
    them out if their absolute value is below the threshold given.

    :Input:
      threshold - (float)
        the tolerance to delete and entry with.
    '''
    if self._slice_format == "dense":
      (N,M,T) = self.shape
      for i in xrange(N):
        for j in xrange(M):
          for t in xrange(T):
            if abs(self._slices[i,j,k]) < threshold:
              self._slices[i,j,k] = 0
    else:
      pass


  def is_equal_to_tensor(self,other, tol = None):
    '''
      This function takes in a another object and a tolerance value and \
    determines whether or not the input tensor is either elementwise equal to \
    or with a tolerance range of another tensor.

    :Input:
      other - (unspecified)
        object to compare the tensor with, may be any time, but will only \
        return true if the input is a Tensor instance
      tol - (float)
        the tolerance to declare whether or not a tensor is elementwise \
        close enough. uses the absolute value, b - tol < a < b + tol.
    :Returns:
      (bool)
        indicates whether or not the two tensors are equal.
    '''
    if tol:
      comp = lambda x,y: abs(x - y) < tol
    else:
      comp = lambda x,y: x == y

    if isinstance(other, Tensor):
      if self.shape == other.shape:
        if self._is_equal_helper(other,comp):
          return other._is_equal_helper(self,comp)
        else:
          return False
      else:
        return False
    else:
      return False

  def _is_equal_helper(self,other,comp):

    if other._slice_format == 'dense':
      for t in xrange(self.shape[2]):
        if self._slice_format == 'dok':
          for ((i,j),v) in self._slices[t].iteritems():
            if not comp(other._slices[i,j,t],v):
              return False
        elif self._slice_format == 'dense':
          for i in xrange(self.shape[0]):
            for j in xrange(self.shape[1]):
              if not comp(other._slices[i,j,t],self._slices[i,j,t]):
                return False
        else:
          if self._slice_format == 'coo':
            slice = self._slices[t]
          else:  # other matrix forms are faster to convert to coo to check
            slice = self._slices[t].tocoo()
          for (i, j, v) in izip(slice.row, slice.col, slice.data):
            if not comp(other._slices[i,j,t], v):
              return False
    else:
      for t in xrange(self.shape[2]):
        # if other is of type coo, change to something one can index into
        if other._slice_format == 'coo':
          other_slice = other._slices[t].todok()
        else:
          other_slice = other._slices[t]

        # iterate over dok differently than others
        if self._slice_format == 'dok':
          for ((i, j), v) in self._slices[t].iteritems():
            if not comp(other_slice[i, j], v):
              return False
        elif self._slice_format == 'dense':
          for i in xrange(self.shape[0]):
            for j in xrange(self.shape[1]):
              if not comp(self._slices[i,j,t],other_slice[i,j]):
                return False
        else:
          if self._slice_format == 'coo':
            slice = self._slices[t]
          else:  # other matrix forms are faster to convert to coo to check
            slice = self._slices[t].tocoo()
          for (i, j, v) in izip(slice.row, slice.col, slice.data):
            if not comp(other_slice[i, j], v):
              return False
    return True

  def todense(self):
    '''
      This function will convert the current tensor instance into a dense \
    tensor, or if make_new is true, will return a dense tensor instance.
    '''
    raise NotImplementedError("condense this function with convert format")


'''-----------------------------------------------------------------------------
                              NON-CLASS FUNCTIONS
-----------------------------------------------------------------------------'''

def zeros(shape, dtype = None,format = 'coo'):
  '''
    This function takes in a tuple indicating the size, and a dtype string \
  compatible with scipy's data types and returns a Tensor instance corresponding \
  to shape passed in filled with all zeros.

  :Input:
    shape - (list or tuple of ints)
      a list or tuple with the dimensions of each of the 3 modes. must be of \
      length 3.
    format - (string)
      the format of the sparse matrices to produce, default is COO.
  :Returns:
    Zero_Tensor - (Tensor Instance)
      an instance of a Tensor of the appropriate dimensions with all zeros.
  '''

  if isinstance(shape,list) or isinstance(shape, tuple):
    if len(shape) == 3:
      for i in range(3):
        if not isinstance(shape[i],int):
          raise TypeError("mode {} dimension must be an integer,\n dimension "
                           "passed in is of type {}\n".format(i,type(i)))
      slices = []
      for t in range(shape[2]):
        slices.append(sp.random(shape[0],shape[1],density=0,format=format))
      return Tensor(slices)
    else:
      raise ValueError("shape must be of length 3.\n")

def random(shape):
  '''
    This function takes in a tuple indicating the size, and a dtype string \
  compatible with scipy's data types and returns a Tensor instance \
  corresponding to shape passed of a given density, .

  :Input:
    shape - (list or tuple of ints)
      a list or tuple with the dimensions of each of the 3 modes. must be of \
      length 3.
    dtype - (dtype)
      a datatype consistent with scipy sparse datatype standards
    format - (string)
      the format of the sparse matrices to produce, default is COO.
    random_state - (int)
      an integer which is passed in as a seed for each of the slices. Each \
      slice will increment the seed value by 1, so each slice will have a \
      unique seed.
  :Returns:
    random_Tensor - (Tensor Instance)
      an instance of a Tensor of the appropriate dimensions with all zeros.
  '''
  raise NotImplementedError("write random function")

def normalize(X,return_sparse_a = True):
  '''
  This function takes in a lateral slice and returns a lateral slice a and \
  lateral slice V with frobenius norm 1 such that V t_prod a is the original \
  lateral slice passed in.

  :Input:
    X - (Tensor Instance)
      the lateral slice passed in to be normalized.
    return_sparse_a - (optional bool)
      a boolean indicating whether or not the lateral slices should be returned \
      as sparse tensor or not.

  :Returns:
    a - (Tensor Instance)
      A lateral slice with the tubal scalars in each of the rows
    V - (Tensor Instance)
      the lateral slice with frobenius norm 1
  '''

  if not isinstance(X,Tensor):
    raise(TypeError("Input must be a Tensor instance\n, X is of type {"
                    "}".format(type(X))))

  (n,m,T) = X.shape
  A = empty((m,1,T))

  V_slices = []

  #compute the fft of the elements in the lateral slice
  for j in range(m):
    if X._slice_format == 'dense':
      slice_fft = rfft(X._slices[:,j,:])
    else:
      slice_fft = np_zeros((n,T))

      # copy the non-zeros in
      for t in xrange(T):
        if X._slice_format == 'dok':
          for ((i,_),v) in X._slices[t][:,j].iteritems():
             slice_fft[i,t] = v
        else:
          slice = X._slices[t][:,j]
          if X._slice_format != 'coo':
            slice = slice.tocoo()
          for (i,v) in izip(slice.row,slice.data):
            slice_fft[i,t] = v
      rfft(slice_fft,overwrite_x=True)

    #normalize all the columns
    tubal_scalar_non_zeros = []

    A[j,0,0] = np_norm(slice_fft[:,0])
    for i in range(n):

      slice_fft[i,0] = slice_fft[i,0]/A[j,0,0]

    if T % 2 == 0:
      end_T = (T-1)/2+1
    else:
      end_T = T/2+1


    for t in xrange(1,end_T):

      #compute the norm of the complex components
      norm = (slice_fft[0,2*t-1]**2 + slice_fft[0,2*t]**2)
      for i in xrange(1,n):
        norm += slice_fft[i,2*t-1]**2
        norm += slice_fft[i,2*t]**2

      norm = sqrt(norm)

      #scale entries
      for i in xrange(n):
        slice_fft[i,2*t-1] = slice_fft[i,2*t-1]/norm
        slice_fft[i,2*t] = slice_fft[i,2*t]/norm
      A[j,0,2*t-1] = norm
      A[j,0,2*t] = 0

    if T % 2 == 0:
      A[j,0,-1] = np_norm(slice_fft[:, T / 2])
      for i in xrange(n):
        slice_fft[i, -1] = slice_fft[i, -1] / A[j,0,-1]


    irfft(slice_fft,overwrite_x = True)
    V_slices.append(sp.dok_matrix(slice_fft))


  irfft(A,overwrite_x=True)

  V = Tensor(V_slices)
  V.squeeze()

  if return_sparse_a:
    slices = []
    for t in xrange(T):
      slices.append(sp.dok_matrix((m,1)))
      for j in xrange(m):
        if abs(A[j,0,t]) > 1e-15:
          slices[t][j,0] = A[j,0,t]
    a = Tensor(slices)
  else:
    a = Tensor(A)

  return V,a

def sparse_givens_rotation(A,i,j,i_swap,apply = False):
  '''
    This function takes in a Tensor instance and a row and column and either \
  returns a sparse tensor instance corresponding to the tubal givens \
  rotation corresponding to zeroing out the ith ,jth tubal scalar or it \
  will apply it to the tensor passed in.

  :Input:
    A - (Tensor Instance)
      the tensor to compute the givens rotation for.
    i - (int)
      the row of the tubal scalar to zero out.
    j - (int)
      the column of the tubal scalar to zero out.
    i_swap - (int)
      the second row of the tubal scalar to rotate with respect to.
    apply - (optional boolean)
       a bool which indicates whether or not to the apply the givens rotation to \
      the tensor rather than return a tensor instance corresponding to the \
      givens rotation.
  :Returns:
    Q - (Tensor Instance)
      if apply is False (default), then Q will be the tensor instance to \
      which the

  TODO:
    handle i_swap tests to ensure that i =/= i_swap
  '''
  #check for valid input
  if A._slice_format == 'coo':
    raise ValueError("cannot index into a coo matrix, convert with "
                     "convert_slices methods of Tensor class \n")

  if abs(i) >= A.shape[0]:
    raise ValueError("i is out of bounds, i must be in (-{},{})".format(
      A.shape[0],A.shape[0]))

  if abs(j) >= A.shape[1]:
    raise ValueError("j is out of bounds, j must be in (-{},{})".format(
      A.shape[1],A.shape[1]))
  if abs(i_swap) >= A.shape[0]:
    raise ValueError("i_swap is out of bounds, i_swap must be in (-{},"
                     "{})".format(A.shape[0],A.shape[0]))
  #TODO: handle test for checking i \neq i_swap


  #compute fft of the tubal scalars
  tubal_scalar1 = fftshift(fft(map(lambda x: x[i,j], A._slices)))
  tubal_scalar2 = fftshift(fft(map(lambda x: x[i_swap, j], A._slices)))


  #compute cos(theta) and sin(theta) in fourier domain
  for t in range(A.shape[2]):
    a_mod = abs(tubal_scalar1[t])
    r = a_mod*sqrt(1 + (abs(tubal_scalar2[t])/a_mod)**2)
    tubal_scalar1[t] =  tubal_scalar1[t] / r
    tubal_scalar2[t] =  tubal_scalar2[t] / r

  tubal_scalar2_conj = map(lambda x: conj(x),tubal_scalar2)


  print tubal_scalar1

  #convert back with inverse fftscipy fftpack
  ifft(tubal_scalar1,overwrite_x=True)
  tubal_scalar1 = ifftshift(tubal_scalar1)
  ifft(tubal_scalar2,overwrite_x=True)
  tubal_scalar2 = ifftshift(tubal_scalar2)
  ifft(tubal_scalar2_conj, overwrite_x=True)
  tubal_scalar4 = ifftshift(tubal_scalar2_conj)
  print tubal_scalar1


  if apply:
    pass
  else:
    for t in range(A.shape[2]):
      if t == 0:
        Q_slices = [sp.identity(A.shape[0],format=A._slice_format)]
      else:
        Q_slices.append(sp.random(A.shape[0],A.shape[0],
                           density=0,format=A._slice_format))
      if i_swap < i:
        Q_slices[t][i, i]     = -tubal_scalar2_conj[t]
        Q_slices[t][i_swap, i_swap] =  tubal_scalar2[t]
        Q_slices[t][i, i_swap]   =  tubal_scalar1[t]
        Q_slices[t][i_swap, i]   =  tubal_scalar1[t]
      else:
        Q_slices[t][i_swap, i_swap] =  tubal_scalar1[t]
        Q_slices[t][i, i]     =  tubal_scalar1[t]
        Q_slices[t][i_swap, i]   =  tubal_scalar2[t]
        Q_slices[t][i, i_swap]   = -tubal_scalar2_conj[t]
    return Tensor(Q_slices)


import os

def main():
  os.chdir('/home/ccolle01/Documents/Tensor.py/')
  A = Tensor('demo')
  V,a = normalize(A[:,0,:])

  X = V * a

  print X._slices[0].todense()
  print A[:,0,:]._slices[0].todense()

  print (A[:,0,:] - V * a).frobenius_norm()

if __name__ == '__main__':
  main()