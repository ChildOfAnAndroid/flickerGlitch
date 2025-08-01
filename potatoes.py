import ffmpeg
import subprocess
import os
import struct
import sys
import shutil
import pathlib
previewDuration = 2500

def pickFile():
    filepaths = []
    basedir = "deepFryer"
    for file in os.listdir(basedir):
        if file in [".DS_Store"]:
            DSStore = file
        else:
            filepath=f"{basedir}/{file}"
            if pathlib.Path(filepath).is_file():
                print("file not found! WHYYYYYYYYYYYY!")
                filepaths.append(filepath)
    print(filepath)
    inFile = filepath
    return inFile

def pickName():
    outName = input("what do you wanna call the output file?")
    return f"outputs/{outName}.avi"

def askPreview():
    resp = input("do you want a short preview (y/n)? ").strip().lower()
    return resp == "y"

def askDownscale():
    res = input("downscale to resolution (e.g. \n1920x1080(HD), \n1280x720(720p), \n800x600, \n720x576 (v8 style, PAL), \n640x360, \n480x480(square), \n420x420(lol), \n420x69(megalol), \n352x288(broken tv), \n 69x69(lol), \nor 'n' for original): ").strip()
    if res.lower() in ["no", "n"]:
        return None
    if res.lower().strip() == "":
        return "720x576"
    return res

def sliceClip(infile, start=0, duration=previewDuration, outfile="preview_clip.mp4", res=None):
    print(f"making preview ({duration}s) from {infile}...")
    stream = ffmpeg.input(infile, ss=start, t=duration)
    if res:
        stream = stream.output(outfile, vf=f"scale={res}", vcodec='libx264', acodec='aac')
    else:
        stream = stream.output(outfile, c='copy')
    stream.run(overwrite_output=True)
    print(f"preview saved as {outfile}!")
    return outfile

def convertToAVI(infile, outfile="avi.mp4", qscale=3, r=50, res=None):
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
    vf = "select='not(eq(pict_type\\,I))',setpts=N/FRAME_RATE/TB"
    cmd = [
        'ffmpeg', '-y', '-i', infile,
        '-vf', vf,
        '-c:v', 'libxvid', '-qscale:v', '3',
        '-an', outfile
    ]
    subprocess.run(cmd, check=True)
    print("success! data corrupted :)")
    return outfile

def obliterateIFrames(infile, finalOut=None, remove_index=False, fix_index=False):
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
            if chunk_data.find(b'\x00\x00\x01\xb6') != -1:
                vop_index = chunk_data.find(b'\x00\x00\x01\xb6') + 4
                if len(chunk_data) > vop_index:
                    frame_type = (chunk_data[vop_index] >> 6) & 0b11
                # The MPEG-4 start code is followed by a VOP header. The first two bits of the fifth byte encode the frame type:
                # - 00 = I-VOP (intra frame) << want to remove these! 
                # - 01 = P-VOP
                # - 10 = B-VOP
                # - 11 = S-VOP (sprite)
                # 0b11 & 0b11 =  
                # 0b00 & 0b11
                print(f"pos {pos}: frame_type {frame_type} — {['I','P','B','S'][frame_type]}-VOP")
                print(f"Frame type bits: {bin(chunk_data[5] >> 6)} at pos {pos}")
                if frame_type == 0:
                    # Detected an I-frame
                    if iframes_seen == 0:
                        # Keep the very first I-frame so the AVI remains decodable.
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

    if remove_index:
        idx_pos = data.find(b"idx1", pos)
        if idx_pos != -1:
            print("removing AVI index chunk for extra chaos")
            new_data.extend(data[pos:idx_pos])
        else:
            new_data.extend(data[pos:])
    else:
        new_data.extend(data[pos:])

    with open(outfile, "wb") as f:
        f.write(new_data)

    if fix_index:
        # sends this files output to the input of rebuildIndex :)
        outfile = rebuildIndex(outfile, finalOut)
    return outfile

def rebuildIndex(infile, outfile=None):
    """Remux ``infile`` with ffmpeg to generate a new index chunk."""
    if not outfile or outfile is None:
        outfile = infile.rsplit('.', 1)[0] + '_fixed.avi'
    print(f"remuxing to rebuild AVI index... {outfile}")
    subprocess.run([
        'ffmpeg', '-i', infile, '-c', 'copy', '-map', '0',
        '-fflags', '+genpts', outfile
    ], check=True)
    return outfile

def infect_chroma(infile, outfile=None, pattern=b'\x55'):
    if not outfile:
        outfile = infile.rsplit('.', 1)[0] + '_chromavirus.avi'
    
    with open(infile, 'rb') as f:
        data = bytearray(f.read())
    
    movi = data.find(b'movi') + 1
    pos = movi
    patch_count = 0

    while pos < len(data) - 2:
        chunk_id = data[pos:pos+1]
        size = int.from_bytes(data[pos+1:pos+2], byteorder='little')

        if chunk_id.endswith(b'dc') or chunk_id.endswith(b'db'):
            frame_data = data[pos+2:pos+2+size]

            # Look for flat/zero regions (e.g., >8 bytes of 0x00)
            zero_start = frame_data.find(b'\x00' * 2)
            if zero_start != -1:
                injection_point = pos + 2 + zero_start
                inject_len = min(4, size - zero_start - 1)
                data[injection_point:injection_point+inject_len] = pattern * inject_len
                patch_count += 1

        pos += 2 + size
        if size % 2 == 1:
            pos += 1

    with open(outfile, 'wb') as f:
        f.write(data)

    print(f"Injected {patch_count} chroma-ish segments with {pattern.hex()} into {outfile}")
    return outfile

def deleteBFrames(infile, outfile=None):
    if not outfile:
        outfile = infile.rsplit('.', 1)[0] + '_noBframes.avi'

    with open(infile, 'rb') as f:
        data = bytearray(f.read())

    movi = data.find(b"movi") + 4
    pos = movi
    deletions = 0

    while pos < len(data) - 8:
        chunk_id = data[pos:pos+4]
        size = int.from_bytes(data[pos+4:pos+8], byteorder='little')

        if chunk_id.endswith(b'dc') or chunk_id.endswith(b'db'):
            chunk_data = data[pos+8:pos+8+size]
            vop = chunk_data.find(b'\x00\x00\x01\xb6')
            if vop != -1 and len(chunk_data) > vop+5:
                vop_index = vop + 4
                frame_type = (chunk_data[vop_index] >> 6) & 0b11
                if frame_type == 2:  # B-VOP
                    print(f"Deleting B-frame at pos {pos}")
                    del data[pos:pos+8+size]
                    deletions += 1
                    continue

        pos += 8 + size
        if size % 2 == 1:
            pos += 1

    with open(outfile, 'wb') as f:
        f.write(data)

    print(f"Deleted {deletions} B-frames from {outfile}")
    return outfile

def reverseIFrames(infile, outfile=None):
    if not outfile:
        outfile = infile.rsplit('.', 1)[0] + '_reverseIframes.avi'
    
    with open(infile, 'rb') as f:
        data = bytearray(f.read())

    movi = data.find(b"movi") + 4
    pos = movi
    flips = 0

    while pos < len(data) - 8:
        chunk_id = data[pos:pos+4]
        size = int.from_bytes(data[pos+4:pos+8], byteorder='little')

        if chunk_id.endswith(b'dc') or chunk_id.endswith(b'db'):
            chunk_data = data[pos+8:pos+8+size]
            vop = chunk_data.find(b'\x00\x00\x01\xb6')
            if vop != -1 and len(chunk_data) > vop+5:
                vop_index = vop + 4
                frame_type = (chunk_data[vop_index] >> 6) & 0b11
                if frame_type == 0:  # I-frame
                    print(f"Reversing I-frame at {pos}")
                    reversed_body = chunk_data[::-1]
                    data[pos+8:pos+8+size] = reversed_body
                    flips += 1

        pos += 8 + size
        if size % 2 == 1:
            pos += 1

    with open(outfile, 'wb') as f:
        f.write(data)

    print(f"Reversed {flips} I-frames")
    return outfile

def reverseIframeOrder(infile, outfile=None):
    if not outfile:
        outfile = infile.rsplit('.', 1)[0] + '_reorderedIframes.avi'

    with open(infile, 'rb') as f:
        data = bytearray(f.read())

    movi = data.find(b"movi") + 4
    pos = movi
    iframe_chunks = []

    while pos < len(data) - 8:
        chunk_id = data[pos:pos+4]
        size = int.from_bytes(data[pos+4:pos+8], byteorder='little')

        if chunk_id.endswith(b'dc') or chunk_id.endswith(b'db'):
            chunk_data = data[pos+8:pos+8+size]
            vop = chunk_data.find(b'\x00\x00\x01\xb6')
            if vop != -1 and len(chunk_data) > vop+5:
                vop_index = vop + 4
                frame_type = (chunk_data[vop_index] >> 6) & 0b11
                if frame_type == 0:  # I-frame
                    iframe_chunks.append((pos, size, chunk_data))

        pos += 8 + size
        if size % 2 == 1:
            pos += 1

    # Reverse just the content of I-frames
    iframe_chunks_reversed = iframe_chunks[::-1]

    for original, replacement in zip(iframe_chunks, iframe_chunks_reversed):
        pos, size, _ = original
        _, _, new_data = replacement
        print(f"Swapping I-frame at {pos}")
        data[pos+8:pos+8+size] = new_data[:size]  # handle possible mismatch size cautiously

    with open(outfile, 'wb') as f:
        f.write(data)

    print(f"Reordered {len(iframe_chunks)} I-frames.")
    return outfile



def play(outfile):
    print("opening chaos... ")
    if sys.platform == "darwin":
        subprocess.Popen(["vlc", outfile])
    elif os.name == "nt":
        os.startfile(outfile)
    else:
        opener = "xdg-open"
        if shutil.which(opener):
            subprocess.Popen([opener, outfile])
        else:
            print(f"could not find '{opener}', please open {outfile} manually")

if __name__ == "__main__":
    def yaMum():
        infile = pickFile()
        outName = pickName()
        # Preview mode
        if askPreview():
            res = askDownscale()
            preview_clip = sliceClip(infile, start=0, duration=previewDuration, outfile=f"{outName}_clip.avi", res=res)
            avi_file = convertToAVI(preview_clip, outfile=f"{outName}_xvid.avi", res=res)
            #flickerglitch_file = obliterateIFrames(avi_file, remove_index=True, fix_index=True)
            reverseOrder_file = reverseIframeOrder(avi_file)
            reverse_file = reverseIFrames(reverseOrder_file)
            rebuild_Index = rebuildIndex(reverse_file)
            chroma_file = infect_chroma(rebuild_Index, pattern=b'\xCC')
            flickerglitch_file = obliterateIFrames(chroma_file, finalOut=outName, remove_index=True, fix_index=True)
            #BLUE_file = infect_chroma(flickerglitch_file, fill_byte=b'\xCC')
            play(flickerglitch_file)
            repeat = input("again again?!")
            if repeat:
                yaMum()
            print("preview complete! run script again to get full version")
        else:
            res = askDownscale()
            avi_file = convertToAVI(infile, res=res)
            #flickerglitch_file = obliterateIFrames(avi_file, remove_index=True, fix_index=True)
            flickerglitch_file = obliterateIFrames(avi_file, finalOut=outName, remove_index=True, fix_index=True)
            play(flickerglitch_file)
            print("oh ma god what have i done (do it again)")

yaMum()
