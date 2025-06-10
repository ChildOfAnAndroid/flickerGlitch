import ffmpeg
import subprocess
import os
import struct
import sys
import shutil

def pickFile():
    inFile = input("enter video file path (mp4/mkv/mov/avi): ").strip()
    if not os.path.exists(inFile):
        print("file not found! WHYYYYYYYYYYYY!")
        exit(1)
    return inFile

def askPreview():
    resp = input("do you want a short preview (y/n)? ").strip().lower()
    return resp == "y"

def askDownscale():
    res = input("downscale to resolution (e.g. \n1920x1080(HD), \n1280x720(720p), \n800x600, \n720x576 (v8 style, PAL), \n640x360, \n480x480(square), \n420x420(lol), \n420x69(megalol), \n352x288(broken tv), \n 69x69(lol), \nor 'n' for original): ").strip()
    if res.lower() in ["", "no", "n"]:
        return None
    return res

def sliceClip(infile, start=0, duration=25, outfile="preview_clip.mp4", res=None):
    print(f"making preview ({duration}s) from {infile}...")
    stream = ffmpeg.input(infile, ss=start, t=duration)
    if res:
        stream = stream.output(outfile, vf=f"scale={res}", vcodec='libx264', acodec='aac')
    else:
        stream = stream.output(outfile, c='copy')
    stream.run(overwrite_output=True)
    print(f"preview saved as {outfile}!")
    return outfile

def convertToAVI(infile, outfile=None, qscale=3, r=50, res=None):
    if not outfile: outfile = infile.rsplit('.', 1)[0] + '_xvid.avi'
    print(f"wololo... converting to Xvid AVI... {outfile}")
    cmd = ["ffmpeg", "-y", "-i", infile, "-c:v", "libxvid", "-qscale:v", str(qscale), "-an", "-r", str(r)]
    if res: cmd.extend(["-s", res])
    cmd.append(outfile)
    subprocess.run(cmd, check=True)
    print("wololo... conversion complete!")
    return outfile

def removeIFrames(infile):
    outfile = infile.rsplit('.', 1)[0] + '_flickerglitch.avi'
    print(f"deliberately destroying your file... removing i-frames (keyframes)... {outfile}")
    # re-encode but only copy P/B-frames (flickerglitch style)
    cmd = ['ffmpeg', '-i', infile, '-vf', 'mpdecimate', '-c:v', 'libxvid', '-qscale:v', '3', '-an', outfile]
    subprocess.run(cmd, check=True)
    print("success! data corrupted :)")
    return outfile

def obliterateIFrames(infile, outfile=None):
    if not outfile:
        outfile = infile.rsplit('.', 1)[0] + '_flickerglitch.avi'
    print(f"obliterating I-frames (except the first one)... {outfile}")
    with open(infile, "rb") as f:
        data = f.read()

    movi = data.find(b"movi") + 4
    pos = movi
    new_data = bytearray(data[:movi])  # Copy header up to start of movi
    iframes_seen = 0

    while pos < len(data):
        chunk_id = data[pos:pos+4]
        if len(chunk_id) < 4: break
        size = struct.unpack('<I', data[pos+4:pos+8])[0]
        chunk_data = data[pos+8:pos+8+size]

        if chunk_id.endswith(b'dc') or chunk_id.endswith(b'db'):
            if chunk_data.startswith(b'\x00\x00\x01\xb6'):
                frame_type = (chunk_data[4] >> 6) & 0b11
                if frame_type == 0:
                    if iframes_seen == 0:
                        # Keep the first I-frame!
                        iframes_seen += 1
                    else:
                        print(f"skipping I-frame at {pos}")
                        pos += 8 + size
                        if size % 2 == 1:
                            pos += 1
                        continue
        new_data.extend(chunk_id)
        new_data.extend(struct.pack('<I', size))
        new_data.extend(chunk_data)
        pos += 8 + size
        if size % 2 == 1:
            pos += 1

    new_data.extend(data[pos:])
    tmp_out = outfile + ".tmp"
    with open(tmp_out, "wb") as f:
        f.write(new_data)
    # remux to rebuild the AVI index so players don't show a single frame
    subprocess.run(["ffmpeg", "-y", "-i", tmp_out, "-c", "copy", outfile], check=True)
    os.remove(tmp_out)
    print(f"success! keyframes gone (except first one): {outfile}")
    return outfile

def play(outfile):
    print("opening chaos... ")
    if sys.platform == "darwin":
        subprocess.Popen(["open", outfile])
    elif os.name == "nt":
        os.startfile(outfile)
    else:
        opener = "xdg-open"
        if shutil.which(opener):
            subprocess.Popen([opener, outfile])
        else:
            print(f"could not find '{opener}', please open {outfile} manually")

if __name__ == "__main__":
    infile = pickFile()
    # Preview mode
    if askPreview():
        res = askDownscale()
        preview_clip = sliceClip(infile, start=0, duration=25, outfile="preview_clip.mp4", res=res)
        avi_file = convertToAVI(preview_clip, outfile="preview_clip_xvid.avi", res=res)
        flickerglitch_file = obliterateIFrames(avi_file)
        play(flickerglitch_file)
        print("preview complete! run script again to get full version")
    else:
        res = askDownscale()
        avi_file = convertToAVI(infile, res=res)
        flickerglitch_file = obliterateIFrames(avi_file)
        play(flickerglitch_file)
        print("oh ma god what have i done (do it again)")
