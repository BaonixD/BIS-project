import asyncio
import sys
from pathlib import Path

SCRIPT = """
import json,sys
from pypdf import PdfReader
try:
 import resource
 resource.setrlimit(resource.RLIMIT_CPU,(3,3))
 try: resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912))
 except (ValueError,OSError): pass
except (ImportError,ValueError,OSError): pass
reader=PdfReader(sys.argv[1],strict=True)
if reader.is_encrypted: raise ValueError('encrypted')
count=len(reader.pages)
if not 1 <= count <= 10: raise ValueError('pages')
seen=set()
def inspect(value,depth=0):
 if depth>80: raise ValueError('depth')
 if hasattr(value,'get_object'): value=value.get_object()
 identity=id(value)
 if identity in seen:return
 seen.add(identity)
 if isinstance(value,dict):
  blocked=['/JS','/JavaScript','/OpenAction','/AA','/Launch','/EmbeddedFiles','/XFA']
  blocked+=['/RichMedia','/URI','/SubmitForm','/ImportData']
  if any(k in value for k in blocked):raise ValueError('active content')
  for v in value.values():inspect(v,depth+1)
 elif isinstance(value,list):
  for v in value:inspect(v,depth+1)
inspect(reader.trailer)
print(json.dumps({'pages':count}))
"""


async def validate_pdf(path: Path) -> int:
    import json

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        SCRIPT,
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=5)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise ValueError("Invalid PDF")
    return int(json.loads(output)["pages"])
