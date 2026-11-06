"""Rebuild editable masters, a contact sheet, the intro and loader from the supplied art.
Requires Python, numpy, opencv-python, Pillow, and ffmpeg on PATH (or FFMPEG).
Run from any directory: python motion/render.py
"""
from pathlib import Path
import json
import os
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "frontend/public/motion"
OUT.mkdir(parents=True, exist_ok=True)
NAMES = ["bull", "duck", "crocodile", "falcon", "elephant", "horse", "wordmark"]
LETTERS = list("MORPHY")
# Components in descending ink-area order. Joined letters are split at a
# slanted seam in source coordinates, keeping the original silhouette intact.
MAP = {
    "bull": ["crown","M",("R","P",1018,0.06,550),"Y","H","O","leg","foot"],
    "duck": [("O","P",444,0.0,380),"M","H","R","Y","leg","foot","crown","detail"],
    "crocodile": ["M",("R","P",659,0.08,400),"O","Y","H","foot","leg","crown"],
    "falcon": ["R","crown","M","O","H","P","Y","foot"],
    "elephant": ["crown",("H","Y",615,-0.07,300),"M","R","P","O","foot"],
    "horse": ["M","Y","R","H","O","foot","P","leg"],
}
# Foreground extracted from the reference masks, with the generated study
# sheet divided at its exact cell boundaries.
def components(mask):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype("uint8"))
    ids = sorted(range(1,count), key=lambda n: -stats[n,cv2.CC_STAT_AREA])
    return [labels == n for n in ids if stats[n,cv2.CC_STAT_AREA] >= 25]

def rings(mask, scale, offset):
    contours, tree = cv2.findContours(mask.astype("uint8"),cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    result = {0:[], 1:[]}
    if tree is None: return result
    for c, info in zip(contours,tree[0]):
        if abs(cv2.contourArea(c)) < 5: continue
        pts = c[:,0,:].astype(float)
        if (cv2.contourArea(c,oriented=True)>0) != (info[3]<0): pts=pts[::-1]
        pts = np.vstack((pts,pts[:1]))
        distances=np.r_[0,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))]
        samples=np.linspace(0,distances[-1],192,endpoint=False)
        ring = np.column_stack([np.interp(samples,distances,pts[:,k]) for k in range(2)])
        result[int(info[3]>=0)].append((abs(cv2.contourArea(c)),ring*scale+offset))
    return {t:[p for _,p in sorted(rs,key=lambda x:-x[0])] for t,rs in result.items()}

def pose(name,img):
    dark = img.min(2)<110
    blue = (img[:,:,0].astype(int)-img[:,:,2].astype(int)>65) & dark
    # The original crocodile is green. Re-ink it along with the bull in black.
    if name not in ("falcon","horse"): blue[:]=False
    y,x=np.where(dark)
    scale=min(768/(x.max()-x.min()+1),430/(y.max()-y.min()+1))
    offset=np.array([480-(x.max()+x.min())*scale/2,270-(y.max()+y.min())*scale/2])
    parts={}
    for i,m in enumerate(components(dark & ~blue)):
        labels=MAP.get(name,LETTERS)
        label=labels[i] if i<len(labels) else "detail"
        if isinstance(label,tuple):
            left,right,at,slope,cy=label
            yy,xx=np.indices(m.shape)
            cut=xx<at+(yy-cy)*slope
            halves=[(left,m & cut),(right,m & ~cut)]
        else: halves=[(label,m)]
        for k,v in halves: parts[k]=parts.get(k,False)|v
    if blue.any(): parts["accent"]=blue
    return {k:rings(v,scale,offset) for k,v in parts.items()}

def wordmark():
    canvas=Image.new("RGB",(1100,300),"white")
    d=ImageDraw.Draw(canvas)
    fonts=[Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts/ariblk.ttf","DejaVuSans-Bold.ttf"]
    for f in fonts:
        try: font=ImageFont.truetype(str(f),180); break
        except OSError: continue
    x=15
    for l in LETTERS:
        d.text((x,0),l,font=font,fill="black"); x+=int(d.textlength(l,font=font))+9
    img=np.array(canvas)
    parts=sorted(components(img.min(2)<120),key=lambda m:np.where(m)[1].min())
    yy,xx=np.where(img.min(2)<120); sc=768/(xx.max()-xx.min())
    off=[480-(xx.max()+xx.min())*sc/2,270-(yy.max()+yy.min())*sc/2]
    return {l:rings(m,sc,off) for l,m in zip(LETTERS,parts)}

def align(a,b):
    # Choose cyclic correspondence by normalized shape rather than bounding box.
    ac=a-a.mean(0); bc=b-b.mean(0)
    return np.roll(b,min(range(len(b)),key=lambda k:np.sum((ac-np.roll(bc,k,axis=0))**2)),axis=0)

def geometry():
    src=HERE/"sources"
    sheet=cv2.imread(str(src/"studies.png")); h,w=sheet.shape[:2]
    cells=[sheet[i*h//2:(i+1)*h//2,j*w//2:(j+1)*w//2] for i in range(2) for j in range(2)]
    imgs=[cv2.imread(str(src/"bull.jpeg")),cells[0],cv2.imread(str(src/"crocodile.jpeg")),*cells[1:]]
    poses=[pose(n,im) for n,im in zip(NAMES,imgs)]+[wordmark()]
    groups=LETTERS+["crown","leg","foot","detail","accent"]
    frames=[{} for _ in poses]
    for g in groups:
        counts=[max(len(p.get(g,{}).get(t,[])) for p in poses) for t in (0,1)]
        for i,p in enumerate(poses):
            anchor=p.get(g,p.get({"crown":"M","foot":"R","leg":"H","accent":"M"}.get(g,"O"),p["M"]))[0][0].mean(0)
            rs=[]
            for t in (0,1):
                real=p.get(g,{}).get(t,[])
                for j in range(counts[t]):
                    a=real[j] if j<len(real) else np.tile(anchor,(192,1))
                    if i: a=align(np.array(frames[i-1][g][len(rs)]),a)
                    rs.append(a.round(2).tolist())
            frames[i][g]=rs
    return frames

def paths(rs):
    return " ".join("M"+" L".join("%.2f,%.2f"%tuple(p) for p in r)+" Z" for r in rs if np.ptp(r,axis=0).max()>0.1)

def draw(frame,size):
    width,height=size; pic=np.full((height,width,3),255,np.uint8)
    for g,rs in frame.items():
        pts=[np.round(np.array(r)*width/960*16).astype(np.int32) for r in rs if np.ptp(r,axis=0).max()>0.1]
        if pts: cv2.fillPoly(pic,pts,(255,71,0) if g=="accent" else (0,0,0),lineType=cv2.LINE_AA,shift=4)
    return pic

def transitions(frames, seq):
    # Painted midpoint guides. The letter block follows an arc while the
    # silhouette changes sides. Preserve counters in the identity's middle.
    # (body height, slope, arch, horizontal shear) per anatomical bridge.
    guides=[(1.16,-.09,24,-.12),(.76,.03,12,.16),(.94,-.18,30,.22),
            (1.30,.13,-18,-.12),(1.13,-.10,18,.18),(1.02,-.03,6,.04)]
    segments=[]
    for i,(first,last) in enumerate(zip(seq,seq[1:])):
        a,b=frames[first],frames[last]
        stretch,slope,arch,shear=guides[i]
        middle={}
        for g in a:
            if g in LETTERS:
                guide=frames[6][g].copy()
                x=guide[:,:,0].copy()-480
                y=guide[:,:,1].copy()-270
                guide[:,:,0]=480+.89*x+shear*y
                guide[:,:,1]=270+stretch*y+slope*x+arch*(x/384)**2
                middle[g]=np.array([align(ra,rm) for ra,rm in zip(a[g],guide)])
            else:
                mid=(a[g]+b[g])*.5
                # Sweep appendages toward the closest glyph instead of
                # leaving disjoint flippers, horns or feet in free space.
                near={"crown":"M","foot":"R","leg":"H","accent":"M","detail":"O"}[g]
                anchor=middle[near][0].mean(0)
                middle[g]=anchor+(mid-anchor)*(.56 if g=="crown" else .28)
        end={g:np.array([align(rm,rb) for rm,rb in zip(middle[g],b[g])]) for g in a}
        segments.append((a,middle,end))
    return segments

def sample(segments,progress):
    # Two smooth intervals pass through an explicit editable bridge drawing.
    phase=progress*len(segments); i=min(int(phase),len(segments)-1)
    u=np.clip((phase-i-.21)/.66,0,1)*2
    a,m,b=segments[i]
    start,finish=(a,m) if u<1 else (m,b)
    t=u if u<1 else u-1
    t=t*t*(3-2*t)
    return {g:r+(finish[g]-r)*t for g,r in start.items()}

def encode(frames,seq,secs,size,target):
    ff=os.environ.get("FFMPEG","ffmpeg")
    cmd=[ff,"-y","-loglevel","error","-f","rawvideo","-pixel_format","bgr24","-video_size",
         "%dx%d"%size,"-framerate","60","-i","-","-an","-c:v","libx264","-threads","4","-preset","veryfast","-crf","16","-pix_fmt","yuv420p","-movflags","+faststart",str(target)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    segments=transitions(frames,seq)
    for i,(_,middle,_) in enumerate(segments):
        folder=HERE/"bridges"/target.stem
        folder.mkdir(parents=True,exist_ok=True)
        svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">'
        for g,rs in middle.items():
            svg+='<path id="%s" fill="%s" fill-rule="evenodd" d="%s"/>'%(g,"#0047ff" if g=="accent" else "#000",paths(rs))
        (folder/("%02d.svg"%(i+1))).write_text(svg+"</svg>")
    for i in range(secs*60):
        proc.stdin.write(draw(sample(segments,i/(secs*60)),size).tobytes())
    proc.stdin.close()
    if proc.wait(): raise RuntimeError("MP4 encode failed")
    subprocess.run([ff,"-y","-loglevel","error","-i",str(target),"-c:v","libvpx-vp9","-threads","4","-row-mt","1","-deadline","realtime","-cpu-used","8","-crf","25","-b:v","0",str(target.with_suffix(".webm"))],check=True)

if __name__=="__main__":
    data=geometry()
    for name,f in zip(NAMES,data):
        svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540"><title>MORPHY '+name+'</title>'
        for g,rs in f.items():
            svg+='<path id="%s" fill="%s" fill-rule="evenodd" d="%s"/>'%(g,"#0047ff" if g=="accent" else "#000",paths(rs))
        (OUT/(name+".svg")).write_text(svg+"</svg>")
    frames=[{g:np.array(rs) for g,rs in f.items()} for f in data]
    sheet=Image.new("RGB",(1440,650),"white"); d=ImageDraw.Draw(sheet)
    for i in range(6):
        col,row=i%3,i//3; x,y=480*col,325*row
        sheet.paste(Image.fromarray(draw(frames[i],(480,270))[:,:,::-1]),(x,y))
        d.text((x+20,y+278),NAMES[i].upper(),fill="black",font=ImageFont.truetype("arialbd.ttf",22))
        d.line((x,y+324,x+479,y+324),fill="black",width=2)
    sheet.save(HERE/"six-poses.png")
    intro=[0,1,2,3,4,5,6]
    # Align the wraparound separately to avoid a closing contour twist.
    frames.append({g:np.array([align(a,b) for a,b in zip(frames[5][g],rs)]) for g,rs in frames[0].items()})
    encode(frames,intro,8,(1920,1080),OUT/"intro.mp4")
    encode(frames,[0,1,2,3,4,5,7],6,(480,270),OUT/"loader.mp4")

