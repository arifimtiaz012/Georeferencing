Currently a GCP (Ground Control Points) extractor from shapefile

This is assuming that I'm starting with shapefile data. 
Shapefiles contain vector data but georeferencing is mostly done on raster data.
That's why this is generating the raster data from the shapefiles, so that I can then georeference it.
The GCPs are extracted: they will be used to do the georeferencing.

The GCP coordinates (if I understand right) are the latitude, longitude coordinates. But its not the fully completed georeference process. 
The georeference process uses the GCP coordinates to then get and align raster images.

Needs a method added to do the actual georeference.

Also, very possible that I was not supposed to be working on shapefile data and instead on the actual jpeg saatellite data. Write code for this case as well.
