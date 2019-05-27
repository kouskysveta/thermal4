// C function for subtracting thermal frames & doing pixel correction
// put compiled ".so" file in /usr/local/lib/python2.7/dist-packages (normally done by install function)
//Put "eeg-info file in /usr/local/lib/python2.7/dist-packages/PackageName-1.0.egg-info (also done by install)

#include </usr/include/python2.7/Python.h> //must be first before any other includes


#include <math.h>
#include <stdlib.h>

static PyObject *
pixelmathA_strip2col(PyObject *self, PyObject *args)
{
//Strip off the 2 columns on the right edge
    unsigned short *imgbfr;
    int lenimg;
    unsigned short *stripbfr;
    int lenstrip;
    unsigned short *last2col; //buffer for the 2 columns in case they are useful for something
    int lenlast2col;
    int row=0, col=0;

    if (!PyArg_ParseTuple(args, "w#w#w#", &imgbfr, &lenimg, &stripbfr, &lenstrip, &last2col, &lenlast2col))
           return NULL;

     for(row=0; row<156; row++){
        for(col=0; col<206; col++){
                  stripbfr[row*206+col] = imgbfr[row*208+col];
         } //end of for column
        for(col=206; col<208; col++){
                  last2col[row*2+col-206] = imgbfr[row*208+col];
         } //end of for column
      } //end of for row

Py_INCREF(Py_None);
return Py_None;        //more typically used is: return Py_BuildValue("i", sts);
}

static PyObject *
pixelmathA_addimages(PyObject *self, PyObject *args)
{
//Add up diffs for pixel scaling factor generation--since Python takes too long
    unsigned short *ret9;
    int len9;
    unsigned short *calbfr;
    int lencal;
    unsigned int *sumofimg; 
    int lensum;
    int ix, imgw=206, imgh=156, nimage=0, firstimg=0;

    if (!PyArg_ParseTuple(args, "w#w#w#iiii", &ret9, &len9, &calbfr, &lencal, &sumofimg, &lensum, &imgw, &imgh, &nimage, &firstimg) )
           return NULL;

     ix = 0;
     while(ix < imgw*imgh){ //sumofimg is actually sum of diffs here
       if (nimage == firstimg +1) sumofimg[ix] = ret9[ix] - calbfr[ix];
         else sumofimg[ix] = sumofimg[ix] + ret9[ix] - calbfr[ix];
       ix=ix+1;
        }//end of while ix


Py_INCREF(Py_None);
return Py_None;        //more typically used is: return Py_BuildValue("i", sts);
}

static PyObject *
pixelmathA_scaleimg(PyObject *self, PyObject *args)
{
//Scale the image to see if Rpi runs full frame rate then
    unsigned char *rgbbfr;
    int lenrgb;
    unsigned char *scalebfr;
    int lenscale, scale=2;
    int vscl=4, hscl=4, row=0, col=0, clr=0;

    if (!PyArg_ParseTuple(args, "w#w#i", &rgbbfr, &lenrgb, &scalebfr, &lenscale, &scale))
           return NULL;

vscl=hscl=scale;

//  for(ix=0; ix<32448; ix++){   pixel=row*208+col
     for(row=0; row<156; row++){
        for(col=0; col<208; col++){
          for(hscl=0; hscl<scale; hscl++){
             for(vscl=0; vscl<scale; vscl++){
                for(clr=0; clr<3; clr++){
                  scalebfr[3*( (scale*row+vscl)*scale*208+scale*col+hscl) + clr] = rgbbfr[3*(row*208+col) + clr];
                } //end of for color
              } //end of for vscale factor
           } //end of for hscale factor
         } //end of for column
      } //end of for row
//    } //end of for pixel

Py_INCREF(Py_None);
return Py_None;        //more typically used is: return Py_BuildValue("i", sts);
}

static PyObject *
pixelmathA_swapBandR(PyObject *self, PyObject *args)
{
//Swap blue & red color bytes because PIL wants RGB & cv2 wants BGR
    unsigned char *rgbbfr;
    int lenrgb;
    int ix=0;
    unsigned char temp;

    if (!PyArg_ParseTuple(args, "w#", &rgbbfr, &lenrgb))
           return NULL;

  for(ix=0; ix<32448; ix++){
    temp =  rgbbfr[ix*3];
    rgbbfr[ix*3] = rgbbfr[(3*ix)+2];
    rgbbfr[(3*ix)+2] = temp;
    }

Py_INCREF(Py_None);
return Py_None;        //more typically used is: return Py_BuildValue("i", sts);
}

static PyObject *
pixelmathA_shuttercal(PyObject *self, PyObject *args)
{
    unsigned  char *ret9;
    unsigned  char *calbfr;
    unsigned  char *tamfx22;
    unsigned char *rgbbfr;
    unsigned  char *badpxls;
    unsigned char *bwbfr;
    unsigned char *kclrs;
    unsigned char *diffcurve;
    unsigned char *basevalues;
    short int *negoffsets;
    short int *shutterref;
    unsigned char *mintamfbfr;
    unsigned char *maxtamfbfr;
    int len9;
    int lencal;
    int lentamf;
    int lenrgb;
    int lenbad;
    int lenbw;
    int lenklrs;
    int lencurve;
    int lenbase;
    int lenoffsets;
    int lenshutterref;
    int lenmintamfbfr;
    int lenmaxtamfbfr;
    int sensrref=8000;
    int bwcolor=0;
    int pixelcorr=0;
    int noraster=0;
    int listfile = 0;
    int sensorloc = 0;
    int curvebase = 2000;
    int diff=1000;
    int pixeloncurve = 0;
    short int base = 0;
    int baseoffset = 0;
    int applyoffs = 1;
    int average5 = -1;
    int ForC = 1;
    int mkr1tamf = 0;
    int tzoom = 0;
    int imgw = 208;
    int imgh = 156;
    int palctr=10;
    int tamfctr;
    short int mintamf=14;
    short int maxtamf=15;
    int numberofcolors=255;
    int clrsperdeg=5;
    float tamfsperdeg=21.95;
    float degcolors=1.1;
    int minpixl = 3, maxpixl = 35;

    int ix = 0;
    unsigned char pixlcorrfactor = 100;
    int objtemp = 0;
    int shutter = 1000;
    int useshuttercal = 1;
    int bcorr = 5;


short int diffs[32448], scaleddiffs[32448], tamfs[32448];
int row = 0, col = 0, ot = 0;
short int otbfr[32448];

    if (!PyArg_ParseTuple(args, "w#w#w#w#w#w#w#w#w#w#w#w#w#iiiiiiiiiiiiiiiiiif", &ret9, &len9, &calbfr, &lencal, &tamfx22, &lentamf, &rgbbfr, &lenrgb, &kclrs, &lenklrs, &badpxls, &lenbad, &bwbfr, &lenbw, &diffcurve, &lencurve, &basevalues, &lenbase, &negoffsets, &lenoffsets, &shutterref, &lenshutterref, &mintamfbfr, &lenmintamfbfr, &maxtamfbfr, &lenmaxtamfbfr, &sensrref, &curvebase, &bwcolor, &pixelcorr, &noraster, &listfile, &applyoffs, &average5, &useshuttercal, &ForC, &mkr1tamf, &tzoom, &imgw, &imgh, &palctr, &tamfctr, &numberofcolors, &clrsperdeg, &tamfsperdeg)) /*see:https://docs.python.org/2/extending/extending.html#extracting-parameters-in-extension-functions */
           return NULL;


            //obtain value of 2nd pixel for use in determining sensor location on curve
            sensorloc = sensrref - (ret9[2]+256*ret9[3]); //the diff value that defines shutter temperature on the curve

               baseoffset =72;

     for (ix =0; ix< imgw*imgh; ix++)
               {  //Subtracting the cal frame from image yields POSITIVE AND NEGATIVE numbers!
               pixlcorrfactor = 100;
               //shutter cal adjusts cal frame to make it as if shutter were viewed through the lens
        //       if( (shutterref[ix] < 900) || (useshuttercal < 0)) shutter = 1000;
          //       else shutter = shutterref[ix];
               diffs[ix] = ( ((ret9[2*ix]+256*ret9[2*ix+1])-shutter*(calbfr[2*ix]+256*calbfr[2*ix+1])/1000) );
               if( ( (abs(diffs[ix]) < 6)  & (noraster >0) ) | ( (badpxls[ix] < 10.5) & (abs(diffs[ix]) > 6) & (pixelcorr >0))  ){
                  diffs[ix] = diffs[ix-1]; //set value = to prior value if is a zero pixel or too low corr factor
                  }
                }

shutter = 100; //Use 100 when using shutter cal for bias current correction--tried 6-27-16 & it only made things a bit worse; did nothing for the pattern
int biasdiff = 0;
     for (ix =0; ix< imgw*imgh; ix++)
               {//calculate scaled (corrected) diffs
                if ( (pixelcorr >0)  & (badpxls[ix] > 10.5) ) pixlcorrfactor = badpxls[ix];
                if(useshuttercal > 10) {
                    biasdiff = (calbfr[2*ix]+256*calbfr[2*ix+1]) - shutterref[ix];
                    if(biasdiff > 1500) shutter = 110;
                      else if(biasdiff < -1500) shutter = 90;
                        else shutter = 100;
                   }//end of shutter (bias) correction
                 scaleddiffs[ix] = 10000*diffs[ix]/(pixlcorrfactor*shutter);//do both pixel scaling & bias corr. in one line
               }// End of for calc scaled diffs


   if(useshuttercal > 0) {
     for (ix =0; ix< imgw*imgh; ix++){
         if (  (badpxls[ix] > 10) ) pixlcorrfactor = badpxls[ix];
         biasdiff = 100*((calbfr[2*ix]+256*calbfr[2*ix+1]) - shutterref[ix])/(int)(pixlcorrfactor);//scale it!
         if(biasdiff > 450) shutter = 104 ;
            else if(biasdiff < -450) shutter = 93;
            else shutter = 100;
            scaleddiffs[ix] = shutter*scaleddiffs[ix]/100;
            }
      }//end of shutter (bias) correction

  if( (average5 >0 ) ) {  //Try averaging diffs instead of tamf
    for (ix =0; ix< imgw*imgh; ix++) //Average surrounding pixels 
    {  
     row = ix/imgw;
     col = ix - row*imgw;
              // if( (shutterref[ix] < 9) || (useshuttercal < 0)) shutter = 100;
               //  else shutter = shutterref[ix];

     if(  (row >=1) && (row < 155) && (col > 0) && (col < 207) ) //Average surrounding pixels
       {
         ot = scaleddiffs[ix] //center pixel

                + scaleddiffs[ix-1] //left pixel
                + scaleddiffs[ix+1] //right pixel
                + scaleddiffs[ix-imgw] //pixel above
                + scaleddiffs[ix+imgw] //pixel below

              + scaleddiffs[ix-(imgw+1)] //upper left pixel
              + scaleddiffs[ix-(imgw-1)]  //upper right pixel
              + scaleddiffs[ix+(imgw-1)] //lower left pixel
              + scaleddiffs[ix+(imgw+1)]; //lower right pixel

         otbfr[ix] = 100*(ot/9)/shutter; //Average value

       }//end of if row & col not at ends

        else otbfr[ix] = 100*scaleddiffs[ix]/shutter;

    }//end of for

     for (ix =0; ix< imgw*imgh; ix++) { //put averaged diffs back into their array
         scaleddiffs[ix] = otbfr[ix];
         }//end of for putting data back in array
   }//end of if avg5


     for (ix =0; ix< imgw*imgh; ix++)
               {//put scaled (corrected) diffs in unused array to pass back to main program
                 basevalues[2*ix] = scaleddiffs[ix] & 0xff;
                 basevalues[2*ix +1] = scaleddiffs[ix] >> 8;
               }// End of for pass scaled diffs to main



shutter = 100;
     for (ix =0; ix< imgw*imgh; ix++)     
               {// Fill tamf array with temperature above -40.  Must subtract curvebase in order to get index for diffcurve

               base = negoffsets[ix];

               //this IF is necessary only because my frame 4 (just as frame 10) has a row of 0s
               if (base < 1000)  baseoffset = base;
               if (applyoffs < 0) baseoffset = 0;
               pixeloncurve = ((sensorloc  - curvebase + scaleddiffs[ix]));
               if (pixeloncurve < 0) pixeloncurve = 0;
               if (pixeloncurve > lencurve-1) pixeloncurve = lencurve-1;

            //   if( (shutterref[ix] < 9) || (useshuttercal < 0)) shutter = 100;
           //      else shutter = shutterref[ix];
               //22 "pixels" per degree F in frame 9 but keep full resolution for tamf
               tamfs[ix] =100*( (diffcurve[2*pixeloncurve] + 256*diffcurve[2*pixeloncurve+1]))/shutter;

               tamfx22[ix*2+1] =( tamfs[ix] >> 8 ); //put 16 bit temperature in a separate array
               tamfx22[ix*2] = tamfs[ix] & 0xff;

                }//end of for...tamf

if(clrsperdeg == 0)
{ //Find min & max tamf in the frame and autorange the palette
     mintamf = 16000;
     maxtamf = 0;
     for (ix =0; ix< imgw*imgh; ix++){
        if(tamfs[ix] > 0){
        if( tamfs[ix] > maxtamf ){
           maxtamf = tamfs[ix];
           maxpixl = ix;
          }
        if( tamfs[ix] < mintamf ){
           mintamf = tamfs[ix];
           minpixl = ix;}
        }
       }//end of for to find min/max

tamfctr = (mintamf + maxtamf)/2;
degcolors = numberofcolors/( (maxtamf - mintamf)/tamfsperdeg);
mintamfbfr[0] = mintamf & 0xff;
mintamfbfr[1] = mintamf >> 8;
maxtamfbfr[0] = maxtamf & 0xff;
maxtamfbfr[1] = maxtamf >> 8;
mintamfbfr[2] = minpixl & 0xff;
mintamfbfr[3] = (minpixl >> 8) & 0xff;
mintamfbfr[4] = (minpixl >> 16) & 0xff;
maxtamfbfr[2] = maxpixl & 0xff;
maxtamfbfr[3] = (maxpixl >> 8) & 0xff;
maxtamfbfr[4] = (maxpixl >> 16) & 0xff;
    }//end of find min/max temp pixels


  if( (average5 > 10 ) ) { //make it > 10 to skip it while averaging diffs instead
    for (ix =0; ix< imgw*imgh; ix++) //Average surrounding pixels & reload color buffer
    {  
     row = ix/imgw;
     col = ix - row*imgw;
               if( (shutterref[ix] < 9) || (useshuttercal < 0)) shutter = 100;
                 else shutter = shutterref[ix];

     if(  (row >=1) && (row < imgh-1) && (col > 0) && (col < imgw-1) ) //Average surrounding pixels
       {
         ot = tamfs[ix] //center pixel

                + tamfs[ix-1] //left pixel
                + tamfs[ix+1] //right pixel
                + tamfs[ix-imgw] //pixel above
                + tamfs[ix+imgw] //pixel below

              + tamfs[ix-(imgw+1)] //upper left pixel
              + tamfs[ix-(imgw-1)]  //upper right pixel
              + tamfs[ix+(imgw-1)] //lower left pixel
              + tamfs[ix+(imgw+1)]; //lower right pixel

         otbfr[ix] = 100*(ot/9)/shutter; //Average value

       }//end of if row & col not at ends

        else otbfr[ix] = 100*tamfs[ix]/shutter;

    }//end of for

     for (ix =0; ix< imgw*imgh; ix++) { //put averaged temperature back into its array
         tamfx22[ix*2+1] =( otbfr[ix] >> 8 );
         tamfx22[ix*2] = otbfr[ix] & 0xff;
         }//end of for putting data back in array
   }//end of if avg5

float tscale;
if(ForC >0) tscale = 21.94;
  else tscale = 19.72;

 if (bwcolor > 0){ //grayscale image
       for (ix =0; ix< imgw*imgh; ix++)
               {
                 if(average5 >10 ) objtemp = otbfr[ix]/tscale;
                     else objtemp = tamfs[ix]/tscale;
                 bwbfr[ix] = (objtemp-40)*2;//ONLY good for temp above ZERO & below 127--this is to get a good B&W display
                 if (objtemp-40 < 0) bwbfr[ix] = 0; //don't want negative numbers in unsigned char
                 if ((objtemp-40)*2 > 255) bwbfr[ix] = 255; //limit to 8 bits positive                
                 if( ( (abs(diff) < 6)  & (noraster >0) ) | ( (badpxls[ix] < 11.5) & (abs(diff) > 6) & (pixelcorr >0))  ) bwbfr[ix] = bwbfr[ix-1]; 
                 rgbbfr[ix*3] = bwbfr[ix];
                 rgbbfr[(ix*3)+1] = bwbfr[ix];
                 rgbbfr[(ix*3)+2] = bwbfr[ix];//Go ahead & use color since I need it for video
                 }

                 }//end of grayscale

int ofset=0;
int zoomcenter = 0;
int scalezoom = 1;
int mkr1 = 0;
//if((tzoom > 0) && (mkr1tamf < 1) ) mkr1tamf = 2525;
//if(tzoom > 0) {zoomcenter = mkr1tamf/tscale; scalezoom = 2; tamfctr = mkr1tamf;}
int index;

if(clrsperdeg >0) degcolors = clrsperdeg;

 if (bwcolor <0){  //colorize it!
       for (ix =0; ix< imgw*imgh; ix++){
           //    if (applyoffs > 0) ofset = negoffsets[ix]; 
             //    if(average5 > 10 ) objtemp = zoomcenter + scalezoom*(otbfr[ix]-ofset-mkr1)/tscale;
               //      else objtemp = zoomcenter + scalezoom*(tamfs[ix]-ofset-mkr1)/tscale;

                 index = palctr + degcolors*(float)(tamfs[ix] - tamfctr)/tamfsperdeg;
                 if(index < 0) index = 0;
                 if(index > numberofcolors-1) index = numberofcolors-1;

           //      if(objtemp < 0) objtemp =0;
           //      if(objtemp > 665) objtemp =665;
             //     if( (2*tamfs[ix]/tscale - 2*objtemp) >0) objtemp = objtemp +1;//round upward?
                 rgbbfr[ix*3] = kclrs[3*index]; //C would not accept a second subscript here so I had to multiply by 3 & add 1 & 1 in the next 2 lines
                 rgbbfr[(ix*3)+1] = kclrs[1+3*( index)];
                 rgbbfr[(ix*3)+2] = kclrs[2+3*( index)];
                  }//end of for colorize
        }//end of colorize

Py_INCREF(Py_None);
return Py_None;        //more typically used is: return Py_BuildValue("i", sts);
}



struct PyMethodDef pixelmathAMethods[] = {

    {"swapBandR",  pixelmathA_swapBandR, METH_VARARGS,
     "Swap Blue & Red bytes."},

    {"scaleimg",  pixelmathA_scaleimg, METH_VARARGS,
     "scale the image instead of using Python."},

    {"shuttercal",  pixelmathA_shuttercal, METH_VARARGS,
     "Perform Pixel Correction with shutter corr."},

    {"strip2col",  pixelmathA_strip2col, METH_VARARGS,
     "Strip off the 2 useless columns on the right edge."},

    {"addimages",  pixelmathA_addimages, METH_VARARGS,
     "Add up diffs for pixel scaling factor generation."},

    {NULL, NULL, 0, NULL}        /* Sentinel */
};

PyMODINIT_FUNC initpixelmathA(void)
{

    (void) Py_InitModule("pixelmathA", pixelmathAMethods);
}
