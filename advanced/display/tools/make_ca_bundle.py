"""Pack certifi's trusted public roots in the ESP32 Arduino 2.x bundle format.
No network access or private certificates are used. The bundle is a build output.
"""
import base64
from pathlib import Path
import re
import struct
import certifi


def tlv(data, offset=0):
    start=offset
    tag=data[offset];offset+=1
    length=data[offset];offset+=1
    if length & 128:
        count=length & 127
        if not 0<count<=4: raise ValueError('Invalid DER length')
        length=int.from_bytes(data[offset:offset+count],'big');offset+=count
    end=offset+length
    if end>len(data): raise ValueError('Truncated DER')
    return tag,data[offset:end],data[start:end],end


def children(data):
    items=[];offset=0
    while offset<len(data):
        tag,body,raw,offset=tlv(data,offset)
        items.append((tag,body,raw))
    return items


def bundle():
    pem=Path(certifi.where()).read_text()
    roots={}
    for block in re.findall(r'-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----',pem,re.S):
        der=base64.b64decode(block)
        _,certificate,_,_=tlv(der)
        tbs=children(children(certificate)[0][1])
        base=1 if tbs[0][0]==0xa0 else 0
        subject,public=tbs[base+4][2],tbs[base+5][2]
        roots[subject]=public
    result=struct.pack('!H',len(roots))
    for subject,public in sorted(roots.items()):
        result+=struct.pack('!HH',len(subject),len(public))+subject+public
    target=Path(__file__).resolve().parents[1]/'.generated/x509_crt_bundle.bin'
    target.parent.mkdir(exist_ok=True)
    if not target.exists() or target.read_bytes()!=result: target.write_bytes(result)
    print(f'Packed {len(roots)} trusted roots from certifi {certifi.__version__}.')

if __name__=='__main__':bundle()
