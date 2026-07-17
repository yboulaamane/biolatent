import { NextResponse } from 'next/server';
import { EMBEDDINGS } from '@/app/data/embeddings';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const search = searchParams.get('search')?.toLowerCase() || '';
  const modality = searchParams.get('modality') || '';
  const representationType = searchParams.get('representationType') || '';
  const inputRepresentation = searchParams.get('inputRepresentation') || '';

  let results = EMBEDDINGS;

  if (search) {
    results = results.filter(
      (emb) =>
        emb.name.toLowerCase().includes(search) ||
        (emb.developer?.toLowerCase() || '').includes(search) ||
        emb.tags.some((tag) => tag.toLowerCase().includes(search))
    );
  }

  if (modality && modality !== 'All') {
    results = results.filter((emb) => emb.modality === modality);
  }

  if (representationType && representationType !== 'All') {
    results = results.filter((emb) => emb.representationType === representationType);
  }

  if (inputRepresentation && inputRepresentation !== 'All') {
    results = results.filter((emb) => emb.inputRepresentation === inputRepresentation);
  }

  return NextResponse.json({
    count: results.length,
    results,
  });
}
