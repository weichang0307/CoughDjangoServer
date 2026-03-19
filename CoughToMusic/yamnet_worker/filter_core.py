import os, numpy as np, librosa, soundfile as sf
from scipy import signal
from noisereduce import reduce_noise
from yamnet_loader import get_yamnet_model
from keras_yamnet.preprocessing import preprocess_input
import soundfile as sf
from scipy.signal import resample

COUGH_CLASS=42
CONFIDENCE_THRESHOLD=0.15
WIN_SIZE_SEC=0.975
HOP_SEC=0.10
PADDING_SEC=0.15
COUGH_END_TIME=0.20
MIN_COUGH_DURATION=0.10
MERGE_GAP_SEC=0.25
SMOOTH_K=3
ENERGY_PERCENTILE=85
ENERGY_FRAME_MS=20
ENERGY_HOP_MS=10
ENERGY_DILATION_MS=40

def detect_cough_with_yamnet(audio, sr):
    model=get_yamnet_model()
    win=int(WIN_SIZE_SEC*sr); hop=max(1,int(HOP_SEC*sr))
    pad=int(PADDING_SEC*sr); merge_gap=int(MERGE_GAP_SEC*sr); min_dur=int(MIN_COUGH_DURATION*sr)
    high_th=CONFIDENCE_THRESHOLD; low_th=max(0.05, high_th*0.6)
    hangover_frames=int(max(COUGH_END_TIME,0.20)/HOP_SEC)
    starts=list(range(0,max(1,len(audio)-win+1),hop))
    probs=[]
    for s in starts:
        e=s+win
        chunk=audio[s:e]
        if not np.any(chunk): probs.append(0.0); continue
        pre=preprocess_input(chunk, sr)
        p=get_yamnet_model().predict(np.expand_dims(pre,0),verbose=0)[0][COUGH_CLASS] if model is None else model.predict(np.expand_dims(pre,0),verbose=0)[0][COUGH_CLASS]
        probs.append(float(p))
    if not probs: return []
    sma=np.convolve(probs, np.ones(SMOOTH_K)/SMOOTH_K, mode="same") if len(probs)>=SMOOTH_K else np.asarray(probs,float)
    segs_idx=[]; in_seg=False; seg_start=None; below=0
    for i,p in enumerate(sma):
        if not in_seg:
            if p>=high_th: in_seg=True; seg_start=i; below=0
        else:
            if p>=low_th: below=0
            else:
                below+=1
                if below>=hangover_frames:
                    segs_idx.append((seg_start,i)); in_seg=False; seg_start=None; below=0
    if in_seg: segs_idx.append((seg_start,len(sma)-1))
    if not segs_idx: return []
    segs=[]
    for i0,i1 in segs_idx:
        s=max(0, starts[i0]-pad); e=min(len(audio), starts[i1]+win+pad)
        if e-s>=min_dur: segs.append((s,e))
    if not segs: return []
    segs.sort(); merged=[]; cs,ce=segs[0]
    for s,e in segs[1:]:
        if s<=ce+int(MERGE_GAP_SEC*sr): ce=max(ce,e)
        else: merged.append((cs,ce)); cs,ce=s,e
    merged.append((cs,ce))
    return merged

def bandpass_filter(segment, sr, lowcut=50, highcut_max=7500):
    ny=sr/2; highcut=min(highcut_max, ny*0.95)
    if lowcut>=highcut: lowcut=highcut*0.1
    b,a=signal.butter(4,[lowcut,highcut],btype='band',fs=sr)
    try: return signal.filtfilt(b,a,segment)
    except: return segment

def _energy_gate(y, sr, segments, percentile=ENERGY_PERCENTILE, frame_ms=ENERGY_FRAME_MS, hop_ms=ENERGY_HOP_MS, dilation_ms=ENERGY_DILATION_MS):
    if not segments: return np.zeros_like(y)
    seg_mask=np.zeros_like(y,dtype=bool)
    for s,e in segments: seg_mask[s:e]=True
    fl=max(2,int(frame_ms*sr/1000)); hl=max(1,int(hop_ms*sr/1000))
    rms=librosa.feature.rms(y=y, frame_length=fl, hop_length=hl, center=True)[0]
    n_frames=len(rms)
    centers=np.clip(np.arange(n_frames)*hl+fl//2,0,len(y)-1)
    in_seg=seg_mask[centers]
    if not in_seg.any(): return np.zeros_like(y)
    thr=np.percentile(rms[in_seg], percentile)
    gate=(rms>=thr)
    dil=max(1,int(dilation_ms/max(1,hop_ms)))
    if dil>1: gate=(np.convolve(gate.astype(int), np.ones(dil,dtype=int), mode="same")>0)
    sample_gate=np.zeros_like(y,dtype=bool)
    for i,g in enumerate(gate):
        if not g: continue
        s=i*hl; e=min(s+fl,len(y)); sample_gate[s:e]=True
    sample_gate &= seg_mask
    return np.where(sample_gate, y, 0.0)



def process_audio(
    audio_path,
    sample_rate=None,
    write_mode="mask",
    out_dir=None,
    keep_gain=0.9,
    apply_energy_gate=True,
    force_error=False,
    force_error_message=None,
):
    # --- 使用 soundfile 載入 ---
    if force_error:
        raise RuntimeError(force_error_message or "Forced filter worker failure")

    audio, orig_sr = sf.read(audio_path)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)  # 若為立體聲，轉成單聲道

    sr = orig_sr
    if sample_rate and sample_rate != orig_sr:
        audio = resample(audio, int(len(audio) * sample_rate / orig_sr))
        sr = sample_rate

    try:
        y = reduce_noise(y=audio, sr=sr, prop_decrease=0.5, stationary=False)
        if not np.isfinite(y).all():
            y = np.nan_to_num(y, 0.0, 0.0, 0.0)
        m = np.max(np.abs(y))
        if m > 0:
            y = y / m * keep_gain
    except:
        y = audio.copy()

    segs = detect_cough_with_yamnet(y, sr)
    if not segs:
        sf.write(audio_path, np.zeros_like(audio), sr)
        return {"path": audio_path, "sr": sr, "segments": [], "mode": write_mode, "energy_gate": apply_energy_gate}

    if write_mode == "mask":
        out = np.zeros_like(y)
        dur = 0.0
        for s, e in segs:
            seg = y[s:e]
            seg = seg if len(seg) < 100 else bandpass_filter(seg, sr)
            out[s:e] = seg
            dur += (e - s) / sr
        if apply_energy_gate:
            out = _energy_gate(out, sr, segs)
        sf.write(audio_path, out, sr)
        return {
            "path": audio_path,
            "sr": sr,
            "segments": segs,
            "total_cough_sec": dur,
            "mode": "mask",
            "energy_gate": apply_energy_gate,
            "percentile": ENERGY_PERCENTILE
        }

    elif write_mode == "split":
        if out_dir is None:
            out_dir = os.path.join(os.path.dirname(audio_path), "cough_segments")
        os.makedirs(out_dir, exist_ok=True)
        written = []
        for k, (s, e) in enumerate(segs, 1):
            seg = y[s:e]
            seg = seg if len(seg) < 100 else bandpass_filter(seg, sr)
            if apply_energy_gate:
                seg = _energy_gate(seg, sr, [(0, len(seg))])
            base = os.path.splitext(os.path.basename(audio_path))[0]
            op = os.path.join(out_dir, f"{base}_cough_{k:02d}_{s}_{e}.wav")
            sf.write(op, seg, sr)
            written.append(op)
        return {
            "paths": written,
            "sr": sr,
            "segments": segs,
            "mode": "split",
            "energy_gate": apply_energy_gate,
            "percentile": ENERGY_PERCENTILE
        }

    else:
        raise ValueError("write_mode must be 'mask' or 'split'")


# 範例：
# r=process_audio("your_audio_file.wav", write_mode="mask", apply_energy_gate=True)
# r=process_audio("your_audio_file.wav", write_mode="split", out_dir="out_coughs", apply_energy_gate=True)
