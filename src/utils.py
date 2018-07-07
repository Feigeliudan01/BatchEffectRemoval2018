
import sklearn.preprocessing as prep
import tensorflow as tf

def get_data(path, data_type):
    source_train_data_filename = path+"/source_train_data"
    target_train_data_filename = path+"/target_train_data"
    source_test_data_filename = path+"/source_test_data"
    target_test_data_filename = path+"/source_test_data"
    
    source_train_data = read(source_train_data_filename)
    target_train_data = read(target_train_data_filename)
    if exists(source_test_data_filename):
        source_test_data = read(source_test_data_filename)
        source_train_data, source_test_data= standard_scale(source_train_data, source_test_data)
    else:   
        source_train_data = standard_scale(source_train_data)
        source_test_data = source_train_data
    if exists(source_test_data_filename):    
        target_test_data = read(target_test_data_filename)
        target_train_data, target_test_data= standard_scale(source_train_data, source_test_data)
    else:
        target_test_data = target_train_data
        target_train_data = source_train_data
    # do log transformation for cytof data    
    if data_type == 'cytof':
        source_train_data = preProcessCytofData(source_train_data)
        source_test_data = preProcessCytofData(source_test_data)
        target_train_data = preProcessCytofData(target_train_data)
        target_test_data = preProcessCytofData(target_test_data)
        
    return  source_train_data, target_train_data, source_test_data, target_test_data

def get_models(model_name):
    return getattr(models, model_name)()

def gradient_penalty(real, fake, f):
        def interpolate(a, b):
            shape = tf.concat((tf.shape(a)[0:1], tf.tile([1], [a.shape.ndims - 1])), axis=0)
            alpha = tf.random_uniform(shape=shape, minval=0., maxval=1.)
            inter = a + alpha * (b - a)
            inter.set_shape(a.get_shape().as_list())
            return inter

        x = interpolate(real, fake)
        pred = f(x)
        gradients = tf.gradients(pred, x)[0]
        slopes = tf.sqrt(tf.reduce_sum(tf.square(gradients), reduction_indices=range(1, x.shape.ndims)))
        gp = tf.reduce_mean((slopes - 1.)**2)
        return gp

def trainable_variables(filters=None, combine_type='or'):
    t_var = tf.trainable_variables()
    if filters is None:
        return t_var
    else:
        return tensors_filter(t_var, filters, combine_type)
    
def standard_scale(X_train, X_test):
    preprocessor = prep.StandardScaler().fit(X_train)
    X_train = preprocessor.transform(X_train)
    if X_test is not None:
        X_test = preprocessor.transform(X_test)
    return X_train, X_test    

def preProcessCytofData(data):
    return np.log(1+data)
 
 
class MMD:
    MMDTargetTrain = None
    MMDTargetTrainSize = None
    MMDTargetValidation = None
    MMDTargetValidationSize = None
    MMDTargetSampleSize = None
    kernel = None
    scales = None
    weights = None
    
    def __init__(self,
                 MMDLayer,
                 MMDTargetTrain,
                 MMDTargetValidation_split=0.1,
                 MMDTargetSampleSize=1000,
                 n_neighbors = 25,
                 scales = None,
                 weights = None):
        if scales == None:
            print("setting scales using KNN")
            med = np.zeros(20)
            for ii in range(1,20):
                sample = MMDTargetTrain[np.random.randint(MMDTargetTrain.shape[0], size=MMDTargetSampleSize),:]
                nbrs = NearestNeighbors(n_neighbors=n_neighbors).fit(sample)
                distances,dummy = nbrs.kneighbors(sample)
                #nearest neighbor is the point so we need to exclude it
                med[ii]=np.median(distances[:,1:n_neighbors])
            med = np.median(med)  
            scales = [med/2, med, med*2] # CyTOF    
            print(scales)
        scales = K.variable(value=np.asarray(scales))
        if weights == None:
            print("setting all scale weights to 1")
            weights = K.eval(K.shape(scales)[0])
        weights = K.variable(value=np.asarray(weights))
        self.MMDLayer =  MMDLayer
        MMDTargetTrain, MMDTargetValidation = train_test_split(MMDTargetTrain, test_size=MMDTargetValidation_split, random_state=42)
        self.MMDTargetTrain = K.variable(value=MMDTargetTrain)
        self.MMDTargetTrainSize = K.eval(K.shape(self.MMDTargetTrain)[0])
        self.MMDTargetValidation = K.variable(value=MMDTargetValidation)
        self.MMDTargetValidationSize = K.eval(K.shape(self.MMDTargetValidation)[0])
        self.MMDTargetSampleSize = MMDTargetSampleSize
        self.kernel = self.RaphyKernel
        self.scales = scales
        self.weights = weights

    
    #Calculate the MMD cost
    def cost(self,source, target):
        #calculate the 3 MMD terms
        xx = self.kernel(source, source)
        xy = self.kernel(source, target)
        yy = self.kernel(target, target)
        #calculate the bias MMD estimater (cannot be less than 0)
        MMD = K.mean(xx) - 2 * K.mean(xy) + K.mean(yy)
        #return the square root of the MMD because it optimizes better
        return K.sqrt(MMD);