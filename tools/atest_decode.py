#!/usr/bin/env python3
"""Decode tools/atest.py's beep codes from a recording of the test (MAME -wavwrite or a capture from hardware, from
the program's start): per test the blocks heard (n high beeps, m low = block 8 (n - 1) + m - 1) against those played.
    atest_decode.py <wav>         (numpy: run in the cps3-dev image)"""
import wave,sys,numpy as np
w=wave.open(sys.argv[1]); n=w.getnframes(); R=w.getframerate(); ch=w.getnchannels()
a=np.frombuffer(w.readframes(n),np.int16).reshape(-1,ch)[:,0].astype(float)
win=int(0.01*R); e=np.sqrt(np.convolve(a*a,np.ones(win)/win,'same')); thr=0.25*e.max(); on=e>thr
idx=np.flatnonzero(np.diff(on.astype(int)))+1; edges=np.r_[0,idx,len(on)]
beeps=[]
for s,t in zip(edges[:-1],edges[1:]):
    if on[s] and t-s>0.05*R:
        zc=np.sum(np.diff(np.sign(a[s:t]))!=0)/2/((t-s)/R); beeps.append((s/R,'H' if zc>800 else 'L'))
tests=[];cur=None
for t,c in beeps:
    if cur is None or t-cur[0]>4.8: cur=[t,0,0]; tests.append(cur)
    cur[1 if c=='H' else 2]+=1
B=[0,1,2,3,4,5,6,7,8,12,16,17,20,24,32,33,40,44,48,63]*2
for i,(t,h,l) in enumerate(tests):
    b=B[i] if i<len(B) else None
    got=[k for k in range(64) if (k//8+1,k%8+1)==(h,l)]
    print(f'T{i+1:02d} {t:6.1f}s expect block {b}: heard {h}H {l}L = block {got[0] if got else "?"} {"" if got and got[0]==b else "<<"}')
