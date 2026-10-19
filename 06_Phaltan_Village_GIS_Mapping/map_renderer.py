"""
ArcGIS-style map renderer matching the Bodkewadi reference layout.
- ESRI World Topo basemap visible everywhere
- Raster clipped INSIDE village boundary only
- Title inside frame top-center
- Legend bottom-left with gradient bar (High/Low)
- Compass rose top-right
- Alternating B/W scalebar bottom-left
- Thin red village boundary
- DMS ticks on all 4 sides
"""
import os, math
import numpy as np
import geopandas as gpd
import rasterio
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
from matplotlib.lines import Line2D
from pyproj import Transformer
import contextily as ctx

FONT = 'Times New Roman'
DPI = 600
FIG_SIZE = (10, 13)
BUFFER = 0.20
NODATA = -9999.0
EPSG = 32643
ESRI_TOPO = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}'
STREAM_COLORS = {1:'#c6dbef',2:'#74b9e0',3:'#2196c8',4:'#1565a8',5:'#0d3d82',6:'#05174d'}
STREAM_WIDTHS = {1:0.6,2:1.0,3:1.5,4:2.2,5:3.0,6:4.0}

_to_wgs = Transformer.from_crs(f'EPSG:{EPSG}','EPSG:4326',always_xy=True)
_to_utm = Transformer.from_crs('EPSG:4326',f'EPSG:{EPSG}',always_xy=True)

def _std_bounds(gdf):
    tb = gdf.total_bounds
    bx,by = (tb[2]-tb[0])*BUFFER, (tb[3]-tb[1])*BUFFER
    xmin,ymin,xmax,ymax = tb[0]-bx, tb[1]-by, tb[2]+bx, tb[3]+by
    dx,dy = xmax-xmin, ymax-ymin
    target = FIG_SIZE[0]/FIG_SIZE[1]
    if dx/dy < target:
        pad=(dy*target-dx)/2; xmin-=pad; xmax+=pad
    else:
        pad=(dx/target-dy)/2; ymin-=pad; ymax+=pad
    return xmin,ymin,xmax,ymax

def _fmt_dms(dd, is_lon):
    c = ('E' if dd>=0 else 'W') if is_lon else ('N' if dd>=0 else 'S')
    dd=abs(dd); d=int(dd); m=int((dd-d)*60); s=int(round((dd-d-m/60)*3600))
    if s==60: m+=1; s=0
    if m==60: d+=1; m=0
    return f'{d}°{m:02d}\'{s:02d}"{c}' if s else f'{d}°{m:02d}\'{c}'

def _dms_ticks(lo, hi, is_lon, ref):
    if is_lon:
        c0=_to_wgs.transform(lo,ref)[0]; c1=_to_wgs.transform(hi,ref)[0]
    else:
        c0=_to_wgs.transform(ref,lo)[1]; c1=_to_wgs.transform(ref,hi)[1]
    span=abs(c1-c0)
    step=1
    for s in [15/3600,30/3600,1/60,2/60,5/60,10/60,15/60,30/60,1]:
        if span/s<=8: step=s; break
    start=math.floor(min(c0,c1)/step)*step
    ticks=[(start+i*step) for i in range(int(span/step)+3)]
    ticks=[t for t in ticks if min(c0,c1)<=t<=max(c0,c1)]
    pos,lbl=[],[]
    for t in ticks:
        if is_lon: p=_to_utm.transform(t,_to_wgs.transform(lo,ref)[1])[0]
        else: p=_to_utm.transform(_to_wgs.transform(ref,lo)[0],t)[1]
        pos.append(p); lbl.append(_fmt_dms(t,is_lon))
    return pos,lbl

def _clip_path(ax, gdf):
    poly=gdf.geometry.unary_union
    ps=[poly] if poly.geom_type=='Polygon' else list(poly.geoms)
    paths=[]
    for p in ps:
        v=list(p.exterior.coords)
        c=[MplPath.MOVETO]+[MplPath.LINETO]*(len(v)-2)+[MplPath.CLOSEPOLY]
        paths.append(MplPath(v,c))
    return PathPatch(MplPath.make_compound_path(*paths),transform=ax.transData,fc='none',ec='none')

def _compass(ax, xf, yf):
    xl,yl=ax.get_xlim(),ax.get_ylim()
    cx=xl[0]+xf*(xl[1]-xl[0]); cy=yl[0]+yf*(yl[1]-yl[0])
    r=(yl[1]-yl[0])*0.035
    ax.add_patch(plt.Circle((cx,cy),r*1.3,fc='white',ec='black',lw=1.2,zorder=50,alpha=0.9))
    for dx,dy,l in [(0,1,'N'),(0,-1,'S'),(1,0,'E'),(-1,0,'W')]:
        ax.plot([cx,cx+dx*r],[cy,cy+dy*r],color='black',lw=1.5,zorder=51)
        ax.text(cx+dx*r*1.5,cy+dy*r*1.5,l,ha='center',va='center',fontsize=8,fontweight='bold',fontfamily=FONT,zorder=52)
    ax.annotate('',xy=(cx,cy+r*0.95),xytext=(cx,cy),arrowprops=dict(arrowstyle='->',color='black',lw=2),zorder=53)

def _scalebar(ax):
    xl,yl=ax.get_xlim(),ax.get_ylim()
    mw=xl[1]-xl[0]; mh=yl[1]-yl[0]
    nice=mw*0.20; mag=10**math.floor(math.log10(nice))
    nice=min([1,2,5,10],key=lambda c:abs(c*mag-nice))*mag
    x0=xl[0]+mw*0.04; y0=yl[0]+mh*0.04; bh=mh*0.012
    for i in range(4):
        fc='black' if i%2==0 else 'white'
        ax.add_patch(mpatches.Rectangle((x0+i*nice/4,y0),nice/4,bh,fc=fc,ec='black',lw=0.8,zorder=60))
    ty=y0+bh+mh*0.008
    ax.text(x0,ty,'0',ha='center',fontsize=7,fontfamily=FONT,zorder=61)
    mid=nice/2
    if nice>=1000:
        ax.text(x0+mid,ty,f'{mid/1000:g}',ha='center',fontsize=6,fontfamily=FONT,zorder=61)
        ax.text(x0+nice,ty,f'{nice/1000:g}',ha='center',fontsize=7,fontfamily=FONT,zorder=61)
        ax.text(x0+nice+mw*0.015,y0+bh/2,'Kilometers',ha='left',va='center',fontsize=7,fontfamily=FONT,zorder=61)
    else:
        ax.text(x0+mid,ty,f'{int(mid)}',ha='center',fontsize=6,fontfamily=FONT,zorder=61)
        ax.text(x0+nice,ty,f'{int(nice)}',ha='center',fontsize=7,fontfamily=FONT,zorder=61)
        ax.text(x0+nice+mw*0.015,y0+bh/2,'Meters',ha='left',va='center',fontsize=7,fontfamily=FONT,zorder=61)

def _dms_axes(ax):
    xl,yl=ax.get_xlim(),ax.get_ylim()
    xp,xlb=_dms_ticks(xl[0],xl[1],True,(yl[0]+yl[1])/2)
    yp,ylb=_dms_ticks(yl[0],yl[1],False,(xl[0]+xl[1])/2)
    ax.set_xticks(xp); ax.set_xticklabels(xlb,fontsize=8,fontfamily=FONT)
    ax.set_yticks(yp); ax.set_yticklabels(ylb,fontsize=8,fontfamily=FONT,rotation=90,va='center')
    ax.tick_params(top=True,right=True,labeltop=True,labelright=True,direction='in',length=5)

def render_map(vname, map_type, gdf, out_png, raster_path=None,
               vector_gdf=None, cmap_name='terrain', label='Elevation',
               unit='Mtrs', contour_interval=None, dem_path=None):
    """Unified ArcGIS-style renderer."""
    print(f"    Rendering {map_type}...")
    b = _std_bounds(gdf)
    fig,ax = plt.subplots(1,1,figsize=FIG_SIZE,dpi=DPI,facecolor='white')
    ax.set_xlim(b[0],b[2]); ax.set_ylim(b[1],b[3]); ax.set_aspect('equal')
    
    # Basemap
    try: ctx.add_basemap(ax,crs=f'EPSG:{EPSG}',source=ESRI_TOPO,alpha=1.0,attribution=False,zorder=0,zoom='auto')
    except: pass
    ax.set_xlim(b[0],b[2]); ax.set_ylim(b[1],b[3])
    
    # Raster (clipped inside boundary)
    rmin,rmax=None,None
    if raster_path and os.path.exists(raster_path):
        with rasterio.open(raster_path) as src:
            data=src.read(1).astype(np.float64)
            nd=src.nodata if src.nodata is not None else NODATA
            ext=[src.bounds.left,src.bounds.right,src.bounds.bottom,src.bounds.top]
        data[data==nd]=np.nan; data[np.isinf(data)]=np.nan
        v=data[~np.isnan(data)]
        if len(v)>0:
            rmin,rmax=float(np.nanmin(v)),float(np.nanmax(v))
            cp=_clip_path(ax,gdf); ax.add_patch(cp)
            if map_type in ['ELEVATION', 'SLOPE']:
                hs_data = data
                if map_type == 'SLOPE' and dem_path and os.path.exists(dem_path):
                    with rasterio.open(dem_path) as dem_src:
                        hs_data = dem_src.read(1).astype(np.float64)
                        hs_nd = dem_src.nodata if dem_src.nodata is not None else NODATA
                        hs_data[hs_data==hs_nd]=np.nan; hs_data[np.isinf(hs_data)]=np.nan
                
                ls = mcolors.LightSource(azdeg=315, altdeg=45)
                hs = ls.hillshade(hs_data, vert_exag=1)
                im_hs = ax.imshow(hs, extent=ext, cmap='gray', origin='upper', aspect='equal', zorder=4, interpolation='bilinear')
                im_hs.set_clip_path(cp)
                alpha_val = 0.65
            else:
                alpha_val = 0.85
            im=ax.imshow(data,extent=ext,cmap=cmap_name,origin='upper',aspect='equal',
                         alpha=alpha_val,zorder=5,vmin=rmin,vmax=rmax,interpolation='bilinear')
            im.set_clip_path(cp)
    
    # Vector (streams/contours)
    if vector_gdf is not None and len(vector_gdf)>0:
        if map_type=='STREAM ORDER':
            oc=next((c for c in ['STRM_VAL','StreamOrde','strahler','order','Value'] if c in vector_gdf.columns),None)
            if oc:
                for ov in sorted(vector_gdf[oc].dropna().unique()):
                    o=int(ov)
                    vector_gdf[vector_gdf[oc]==ov].plot(ax=ax,color=STREAM_COLORS.get(o,'#05174d'),linewidth=STREAM_WIDTHS.get(o,1),zorder=10)
            else:
                vector_gdf.plot(ax=ax,color='#1565a8',linewidth=1.2,zorder=10)
        else:
            lw = 0.4 if (contour_interval and int(contour_interval) == 5) else 0.8
            vector_gdf.plot(ax=ax,color='#8B4513',linewidth=lw,alpha=0.85,zorder=10)
    
    # Boundary
    gdf.plot(ax=ax,facecolor='none',edgecolor='red',linewidth=1.5,zorder=20)
    
    # Title inside frame
    ax.text(0.5,0.97,f'{map_type} MAP OF',transform=ax.transAxes,ha='center',va='top',fontsize=14,fontfamily=FONT,zorder=100)
    ax.text(0.5,0.93,vname.upper(),transform=ax.transAxes,ha='center',va='top',fontsize=22,fontfamily=FONT,fontweight='bold',zorder=100)
    
    _compass(ax,0.92,0.93)
    _scalebar(ax)
    
    # Legend
    if raster_path and rmin is not None:
        bx0=b[0]+(b[2]-b[0])*0.02; by0=b[1]+(b[3]-b[1])*0.08
        bw=(b[2]-b[0])*0.28; bh2=(b[3]-b[1])*0.28
        # Legend background removed for transparency
        ax.text(bx0+bw*0.05,by0+bh2*0.95,'Legend',fontsize=10,fontfamily=FONT,fontstyle='italic',fontweight='bold',va='top',zorder=95)
        ax.plot([bx0+bw*0.05,bx0+bw*0.25],[by0+bh2*0.78]*2,color='red',lw=1.5,zorder=95)
        ax.text(bx0+bw*0.30,by0+bh2*0.78,vname,fontsize=8.5,fontfamily=FONT,va='center',zorder=95)
        ax.text(bx0+bw*0.05,by0+bh2*0.65,f'{label}.',fontsize=9,fontfamily=FONT,fontweight='bold',va='top',zorder=95)
        ax.text(bx0+bw*0.05,by0+bh2*0.57,unit,fontsize=8.5,fontfamily=FONT,va='top',zorder=95)
        gx=bx0+bw*0.08; gy=by0+bh2*0.10; gh=bh2*0.42; gw=(b[2]-b[0])*0.025
        grad=np.linspace(rmax,rmin,100).reshape(-1,1)
        ax.imshow(grad,extent=[gx,gx+gw,gy,gy+gh],aspect='auto',cmap=cmap_name,vmin=rmin,vmax=rmax,zorder=95)
        ax.text(gx+gw*1.5,gy+gh,f'High : {rmax:.3f}',fontsize=7.5,fontfamily=FONT,va='top',zorder=95)
        ax.text(gx+gw*1.5,gy,f'Low : {rmin:.3f}',fontsize=7.5,fontfamily=FONT,va='bottom',zorder=95)
    elif map_type=='STREAM ORDER' and vector_gdf is not None:
        oc=next((c for c in ['STRM_VAL','StreamOrde','strahler','order','Value'] if c in vector_gdf.columns),None)
        if oc:
            ords=sorted(vector_gdf[oc].dropna().unique())
            h=[Line2D([0],[0],color='red',lw=1.5,label=vname)]
            h+=[Line2D([0],[0],color=STREAM_COLORS.get(int(o),'#05174d'),lw=STREAM_WIDTHS.get(int(o),1)+0.5,label=f'Order {int(o)}') for o in ords]
            leg=ax.legend(handles=h,title='Legend',loc='lower left',fontsize=8.5,title_fontsize=10,frameon=False,prop={'family':FONT,'size':8.5},bbox_to_anchor=(0.02,0.08))
            leg.get_title().set_fontstyle('italic'); leg.get_title().set_fontweight('bold')
    elif map_type=='BOUNDARY':
        h=[Line2D([0],[0],color='red',lw=1.5,label=vname)]
        leg=ax.legend(handles=h,title='Legend',loc='lower left',fontsize=9,title_fontsize=10,frameon=False,prop={'family':FONT,'size':9},bbox_to_anchor=(0.02,0.12))
        leg.get_title().set_fontstyle('italic'); leg.get_title().set_fontweight('bold')
    elif map_type.startswith('CONTOUR'):
        iv=contour_interval or 10
        h=[Line2D([0],[0],color='red',lw=1.5,label=vname),Line2D([0],[0],color='#8B4513',lw=0.7,label=f'{iv}m Contour')]
        leg=ax.legend(handles=h,title='Legend',loc='lower left',fontsize=9,title_fontsize=10,frameon=False,prop={'family':FONT,'size':9},bbox_to_anchor=(0.02,0.12))
        leg.get_title().set_fontstyle('italic'); leg.get_title().set_fontweight('bold')
    
    _dms_axes(ax)
    for s in ax.spines.values(): s.set_linewidth(1.8); s.set_color('black')
    ax.text(0.98,0.005,'Sources: Esri, HERE, Garmin, Intermap,\nUSGS, FAO, NPS, NRCAN, Esri',transform=ax.transAxes,ha='right',va='bottom',fontsize=5,fontfamily=FONT,color='#555',zorder=100)
    fig.savefig(out_png,dpi=DPI,bbox_inches='tight',facecolor='white',pad_inches=0.1)
    plt.close(fig)
    print(f"    Done: {os.path.basename(out_png)}")
