import os, numpy as np, librosa, soundfile as sf
from scipy import signal
from noisereduce import reduce_noise

BANDPASS_LOW=50
BANDPASS_HIGH_MAX=7500
ENERGY_PERCENTILE=85
ENERGY_FRAME_MS=20
ENERGY_HOP_MS=10
ENERGY_DILATION_MS=40
MIN_KEEP_MS=80
MERGE_GAP_MS=150

def bandpass_filter(y, sr, low=BANDPASS_LOW, high_max=BANDPASS_HIGH_MAX):
    ny=sr/2; high=min(high_max, ny*0.95)
    if low>=high: low=high*0.1
    b,a=signal.butter(4,[low,high],btype='band',fs=sr)
    try: return signal.filtfilt(b,a,y)
    except: return y

def _energy_gate_mask(y, sr, percentile=ENERGY_PERCENTILE, frame_ms=ENERGY_FRAME_MS, hop_ms=ENERGY_HOP_MS, dilation_ms=ENERGY_DILATION_MS):
    fl=max(2,int(frame_ms*sr/1000)); hl=max(1,int(hop_ms*sr/1000))
    rms=librosa.feature.rms(y=y, frame_length=fl, hop_length=hl, center=True)[0]
    base=rms[rms>1e-12]; base=rms if base.size==0 else base
    thr=np.percentile(base, percentile)
    gate=(rms>=thr)
    if not gate.any():
        for p in range(percentile-5, 59, -5):
            thr=np.percentile(base, p)
            gate=(rms>=thr)
            if gate.any(): break
    dil=max(1,int(dilation_ms/max(1,hop_ms)))
    if dil>1: gate=(np.convolve(gate.astype(int), np.ones(dil,dtype=int), mode="same")>0)
    mask=np.zeros_like(y,dtype=bool)
    for i,g in enumerate(gate):
        if not g: continue
        s=i*hl; e=min(s+fl,len(y)); mask[s:e]=True
    return mask

def _mask_to_segments(mask, sr, min_keep_ms=MIN_KEEP_MS, merge_gap_ms=MERGE_GAP_MS):
    idx=np.flatnonzero(mask.astype(int)[1:]-mask.astype(int)[:-1])
    bounds=[]
    prev=0 if mask[0] else None
    for k in idx:
        if prev is None and mask[k]: prev=k+1
        elif prev is not None and not mask[k]: bounds.append((prev, k+1)); prev=None
    if prev is not None: bounds.append((prev, len(mask)))
    if not bounds: return []
    merged=[]
    min_len=int(min_keep_ms*sr/1000); gap=int(merge_gap_ms*sr/1000)
    cs,ce=bounds[0]
    for s,e in bounds[1:]:
        if s-ce<=gap: ce=e
        else:
            if ce-cs>=min_len: merged.append((cs,ce))
            cs,ce=s,e
    if ce-cs>=min_len: merged.append((cs,ce))
    return merged

def process_audio(audio_path, sample_rate=None, write_mode="mask", out_dir=None, keep_gain=0.9,
                  energy_percentile=ENERGY_PERCENTILE, frame_ms=ENERGY_FRAME_MS, hop_ms=ENERGY_HOP_MS,
                  dilation_ms=ENERGY_DILATION_MS, min_keep_ms=MIN_KEEP_MS, merge_gap_ms=MERGE_GAP_MS,
                  apply_noise_reduce=True):
    y, sr = librosa.load(audio_path, sr=sample_rate)
    if apply_noise_reduce:
        try:
            y=reduce_noise(y=y, sr=sr, prop_decrease=0.5, stationary=False)
            if not np.isfinite(y).all(): y=np.nan_to_num(y,0.0,0.0,0.0)
        except: pass
    m=np.max(np.abs(y))
    if m>0: y=y/m*keep_gain
    y=bandpass_filter(y, sr)
    mask=_energy_gate_mask(y, sr, percentile=energy_percentile, frame_ms=frame_ms, hop_ms=hop_ms, dilation_ms=dilation_ms)
    segs=_mask_to_segments(mask, sr, min_keep_ms=min_keep_ms, merge_gap_ms=merge_gap_ms)
    if write_mode=="mask":
        out=np.where(mask, y, 0.0)
        sf.write(audio_path, out, sr)
        tot_sec=sum((e-s)/sr for s,e in segs)
        return {"path":audio_path,"sr":sr,"segments":segs,"total_kept_sec":tot_sec,"mode":"mask",
                "percentile":energy_percentile,"frame_ms":frame_ms,"hop_ms":hop_ms,"dilation_ms":dilation_ms}
    elif write_mode=="split":
        if out_dir is None: out_dir=os.path.join(os.path.dirname(audio_path),"energy_segments")
        os.makedirs(out_dir, exist_ok=True)
        written=[]
        base=os.path.splitext(os.path.basename(audio_path))[0]
        for i,(s,e) in enumerate(segs,1):
            op=os.path.join(out_dir, f"{base}_ener_{i:02d}_{s}_{e}.wav")
            sf.write(op, y[s:e], sr); written.append(op)
        return {"paths":written,"sr":sr,"segments":segs,"mode":"split",
                "percentile":energy_percentile,"frame_ms":frame_ms,"hop_ms":hop_ms,"dilation_ms":dilation_ms}
    
    
    else:
        raise ValueError("write_mode must be 'mask' or 'split'")
    

# 例：
# process_audio("your.wav", write_mode="mask")
# process_audio("your.wav", write_mode="split", out_dir="out_energy")
