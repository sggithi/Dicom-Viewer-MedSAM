from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import QtCore
from PyQt5.QtCore import *
from twoD import edgefunction as ef
import cv2
import numpy as np
import pydicom
from medsam_infer import *
from PIL import Image
import PyQt5.QtGui

from PyQt5.QtGui import (
    QImage,
)
from PyQt5.QtWidgets import (
    QGraphicsScene,
)

#if torch.backends.mps.is_available():
#    device = torch.device("mps")
#else:
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

class QPaintLabel2(QLabel):

    def __init__(self, parent):
        super(QLabel, self).__init__(parent)
        self.window = None
        self.setMouseTracking(False)
        self.setMinimumSize(1, 1)
        self.drawornot, self.seed = False, False
        self.image = None
        self.processedImage = None
        self.imgr, self.imgc = None, None
        self.pos_x = 20
        self.pos_y = 20
        self.imgpos_x = 0
        self.imgpos_y = 0
        self.pos_xy = []
        self.mor_Kersize = 3
        self.mor_Iter = 3
        self.originalImage = None
        
        self.type = 'general'
        self.setMouseTracking(True)
        self.drag_start = None
        self.drag_end = None
        
        self.mask_c =  None
        self.embedding = None
        self.prev_mask = None
        self.color_idx = 0
   


    def mouseMoveEvent(self, event):
        if self.drawornot:
            self.pos_x = event.pos().x()
            self.pos_y = event.pos().y()
            self.imgpos_x = int(self.pos_x * self.imgc / self.width())
            self.imgpos_y = int(self.pos_y * self.imgr / self.height())
            self.pos_xy.append((self.imgpos_x, self.imgpos_y))
            self.drawing()
        
        if event.buttons() & Qt.LeftButton:
            self.drag_end = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_end = event.pos()
            # MARK: Print np Array
            print(np.array([self.drag_start.x(), self.drag_start.y(), self.drag_end.x(), self.drag_end.y()]))
            ex, ey = self.drag_end.x(), self.drag_end.y()
            sx, sy = self.drag_start.x(), self.drag_start.y()
            xmin = min(ex, sx)
            xmax = max(ex, sx)
            ymin = min(ey, sy)
            ymax = max(ey, sy)
            
            H, W, = self.image.shape # 3D H, W, _
            box_np = np.array([[xmin, ymin, xmax, ymax]])
            box_256 = box_np / np.array([W, H, W, H]) * 256

            ########################################################
            # medsam_lite_model(from medsam_infer.py), image embedding, box (256 size)
            # get mask
            sam_mask = medsam_inference(medsam_lite_model, self.embedding, box_256, H, W)
    
            # initialize mask (zero) 
            self.mask_c = np.zeros((W,H), dtype="uint8") # (512, 512)
            
            self.mask_c[sam_mask != 0] = 255
            self.color_idx += 1

            # self.origin imabe + self.mask => masked_image
            masked_image = cv2.add(self.originalImage, self.mask_c)
            self.processedImage = masked_image
         
            # cv2.imshow('Masked Image', masked_image)

            ########################################################
            self.display_image()

            self.update()
            self.drag_start = None
            self.drag_end = None


    def mousePressEvent(self, event):
        if self.drawornot:
            self.pos_x = event.pos().x()
            self.pos_y = event.pos().y()
            self.imgpos_x = int(self.pos_x * self.imgc / self.width())
            self.imgpos_y = int(self.pos_y * self.imgr / self.height())
            self.pos_xy.append((self.imgpos_x, self.imgpos_y))
            self.drawing()
        if self.seed:
            self.pos_x = event.pos().x()
            self.pos_y = event.pos().y()
            self.imgpos_x = int(self.pos_x * self.imgc / self.width())
            self.imgpos_y = int(self.pos_y * self.imgr / self.height())
            self.seed_clicked(seedx=self.imgpos_x, seedy=self.imgpos_y)
            self.seed = False
        if event.button() == Qt.LeftButton:
            self.drag_start = event.pos()
            self.drag_end = event.pos()
            self.update()

# https://stackoverflow.com/questions/7501706/python-how-do-i-pass-variables-between-class-instances-or-get-the-caller
    def edge_detection(self, _type):
        try:
            self.processedImage = cv2.cvtColor(self.processedImage, cv2.COLOR_BGR2GRAY)
        except Exception:
            pass
        self.processedImage = linear_convert(self.processedImage).astype(np.uint8)
        if _type == 'Laplacian':
            self.processedImage = cv2.convertScaleAbs(cv2.Laplacian(self.processedImage, cv2.CV_16S, ksize=1))
        elif _type == 'Sobel':
            img = linear_convert(ef.sobel(self.processedImage)).astype(np.uint8)
            ret, img = cv2.threshold(img, 110, 255, cv2.THRESH_BINARY)
            self.processedImage = img
        elif _type == 'Perwitt':
            img = linear_convert(ef.perwitt(self.processedImage)).astype(np.uint8)
            ret, img = cv2.threshold(img, 70, 255, cv2.THRESH_BINARY)
            self.processedImage = img
        elif _type == 'Frei & Chen':
            img = linear_convert(ef.frei_chen(self.processedImage)).astype(np.uint8)
            ret, img = cv2.threshold(img, 80, 255, cv2.THRESH_BINARY)
            self.processedImage = img

        self.display_image()

    def morthology(self, _type):
        kernel = np.ones((self.mor_Kersize, self.mor_Kersize), np.uint8)

        if _type == 'Dilation':
            self.processedImage = cv2.dilate(self.processedImage, kernel, iterations=self.mor_Iter)
        elif _type == 'Erosion':
            self.processedImage = cv2.erode(self.processedImage, kernel, iterations=self.mor_Iter)
        elif _type == 'Opening':
            self.processedImage = cv2.morphologyEx(self.processedImage, cv2.MORPH_OPEN,
                                                   kernel, iterations=self.mor_Iter)
        elif _type == 'Closing':
            self.processedImage = cv2.morphologyEx(self.processedImage, cv2.MORPH_CLOSE,
                                                   kernel, iterations=self.mor_Iter)

        self.display_image()

    def load_dicom_image(self, fname):
        dcm = pydicom.read_file(fname, force=True)
        # or whatever is the correct transfer syntax for the file
        dcm.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        print(np.nanmax(dcm.pixel_array), np.nanmin(dcm.pixel_array))
        dcm.image = dcm.pixel_array * dcm.RescaleSlope + dcm.RescaleIntercept
        self.image = linear_convert(dcm.image).astype(np.uint8)
        print(self.image)
        if len(self.image.shape) == 2:
            img_3c = np.repeat(self.image[:, :, None], 3, axis=-1)
        else:
            img_3c = self.image
            
        ###########################################################################################
        ######### Get Image embedding when dicom image is uploaded ###############################
        # size (256, 256)
        img_256 = transform.resize(
            img_3c, (256, 256), order=3, preserve_range=True, anti_aliasing=True
        ).astype(np.uint8)
        img_256_norm = (img_256 - img_256.min()) / np.clip(
        img_256.max() - img_256.min(), a_min=1e-8, a_max=None
    )  
        img_256_tensor = (
            torch.tensor(img_256_norm).float().permute(2, 0, 1).unsqueeze(0).to(device)
        )
        print("Getting img embedding")
        
        self.embedding = medsam_lite_model.image_encoder(img_256_tensor) # (1, 256, 64, 64)

        ###########################################################################################
        self.img_3c = img_3c
        self.processedImage = self.image.copy()
        cv2.imshow('Masked Image', self.processedImage)
        self.originalImage = self.processedImage
        self.imgr, self.imgc = self.processedImage.shape[0:2]
        self.display_image()

    def load_image(self, fname):
        print(fname)
        self.image = cv2.imread(fname)
        self.processedImage = self.image.copy()
        self.imgr, self.imgc = self.processedImage.shape[0:2]
        self.display_image()

    def display_image(self):
        qformat = QImage.Format_Indexed8
        if len(self.processedImage.shape) == 3:  # rows[0], cols[1], channels[2]
            if (self.processedImage.shape[2]) == 4:
                qformat = QImage.Format_RGBA8888
            else:
                qformat = QImage.Format_RGB888

        w, h = self.width(), self.height()
        img = QImage(self.processedImage, self.processedImage.shape[1],
                     self.processedImage.shape[0], self.processedImage.strides[0], qformat)
        img = img.rgbSwapped()
        self.setScaledContents(True)
        backlash = self.lineWidth()*2
        self.setPixmap(QPixmap.fromImage(img).scaled(w-backlash, h-backlash, Qt.IgnoreAspectRatio))
        self.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

    def drawing(self):
        self.processedImage[self.imgpos_y:self.imgpos_y+20, self.imgpos_x:self.imgpos_x+20] = 255
        self.display_image()

    def thresholding(self, threshold):
        ret, img = cv2.threshold(self.processedImage, threshold, 255, cv2.THRESH_BINARY)
        self.processedImage = img
        self.display_image()

    def seed_clicked(self, seedx, seedy):
        try:
            self.processedImage = cv2.cvtColor(self.processedImage, cv2.COLOR_BGR2GRAY)
        except Exception:
            pass
        tobeprocessed = self.processedImage.copy()
        result = self.region_growing(tobeprocessed, (seedy, seedx))
        self.processedImage = result
        self.display_image()

    def region_growing(self, img, seed):
        _list = []
        outimg = np.zeros_like(img)
        _list.append((seed[0], seed[1]))
        processed = []
        while len(_list) > 0:
            pix = _list[0]
            outimg[pix[0], pix[1]] = 255
            for coord in get8n(pix[0], pix[1], img.shape):
                if img[coord[0], coord[1]] != 0:
                    outimg[coord[0], coord[1]] = 255
                    if coord not in processed:
                        _list.append(coord)
                    processed.append(coord)
            _list.pop(0)
            self.processedImage = outimg
            self.display_image()
        cv2.destroyAllWindows()
        return outimg
        
    def paintEvent(self, event):
        super().paintEvent(event)
            
        loc = QFont()
        loc.setPixelSize(10)
        loc.setBold(True)
        loc.setItalic(True)
        loc.setPointSize(15)
        
        # MARK: - Bounding Box

        if self.pixmap():
            pixmap = self.pixmap()
            painter = QPainter(self)
            painter.drawPixmap(self.rect(), pixmap)
            
            painter.setPen(QPen(Qt.red, 3))
            if self.drag_start and self.drag_end:
                rect = QRect(self.drag_start, self.drag_end).normalized()
                painter.drawRect(rect)

def np2pixmap(np_img):
    height, width, channel = np_img.shape
    bytesPerLine = 3 * width
    qImg = QImage(np_img.data, width, height, bytesPerLine, QImage.Format_RGB888)
    return QPixmap.fromImage(qImg)

def get8n(x, y, shape):
    out = []
    maxx = shape[1]-1
    maxy = shape[0]-1
    # top left
    outx = min(max(x-1, 0), maxx)
    outy = min(max(y-1, 0), maxy)
    out.append((outx, outy))
    # top center
    outx = x
    outy = min(max(y-1, 0), maxy)
    out.append((outx, outy))
    # top right
    outx = min(max(x+1, 0), maxx)
    outy = min(max(y-1, 0), maxy)
    out.append((outx, outy))
    # left
    outx = min(max(x-1, 0), maxx)
    outy = y
    out.append((outx, outy))
    # right
    outx = min(max(x+1, 0), maxx)
    outy = y
    out.append((outx, outy))
    # bottom left
    outx = min(max(x-1, 0), maxx)
    outy = min(max(y+1, 0), maxy)
    out.append((outx, outy))
    # bottom center
    outx = x
    outy = min(max(y+1, 0), maxy)
    out.append((outx, outy))
    # bottom right
    outx = min(max(x+1, 0), maxx)
    outy = min(max(y+1, 0), maxy)
    out.append((outx, outy))
    return out


def linear_convert(img):
    convert_scale = 255.0 / (np.max(img) - np.min(img))
    converted_img = convert_scale*img-(convert_scale*np.min(img))
    return converted_img
