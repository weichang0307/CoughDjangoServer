from ..keras_yamnet.yamnet import YAMNet

# 用來儲存模型物件的變數
_model = None

def get_yamnet_model():
    global _model
    # 檢查模型是否已經加載過，如果沒有則加載
    if _model is None:
        print("Loading model...")
        _model = YAMNet(weights='C:/Users/DreamalityLab/Desktop/jayden/CoughDjangoServer/CoughToMusic/keras_yamnet/yamnet.h5')
        print("Model loaded!")
    return _model