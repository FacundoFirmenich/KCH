import fs from 'node:fs'
import * as dagCbor from '@ipld/dag-cbor'
import { CID } from 'multiformats/cid'
import { sha256 } from 'multiformats/hashes/sha2'
const doc=JSON.parse(fs.readFileSync(process.argv[2],'utf8'))
const valid=[]
for (const v of doc.valid){
  const bytes=dagCbor.encode(v.value)
  const hash=await sha256.digest(bytes)
  valid.push({id:v.id,hex:Buffer.from(bytes).toString('hex'),cid:CID.create(1,dagCbor.code,hash).toString()})
}
const malformed=[]
for (const v of doc.malformed){
  let rejected=false; let error=null
  try { dagCbor.decode(Buffer.from(v.hex,'hex')) } catch(e){ rejected=true; error=e.constructor?.name ?? 'Error' }
  malformed.push({id:v.id,rejected,error})
}
process.stdout.write(JSON.stringify({valid,malformed}))
