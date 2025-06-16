import rasterio
import matplotlib.pyplot as plt

# TIFF-Datei Pfad
file_path = "/tmp/test_output_ulm/1.tiff"

with rasterio.open(file_path) as src:
    image = src.read(1)
    plt.imshow(image, cmap="gray")
    plt.title("/tmp/test_output_ulm/1.tiff")
    plt.axis('off')
    plt.show()
