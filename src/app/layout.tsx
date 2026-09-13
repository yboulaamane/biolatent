import type { Metadata } from "next";
import { Geist_Mono, Outfit } from "next/font/google";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "BioLatent | Measured Biological Embedding Benchmark",
  description: "A reproducible frozen-embedding benchmark and literature registry for molecular, protein, and genomic representations.",
  keywords: ["embeddings", "drug discovery", "protein language models", "molecular representations", "SMILES", "ESM-2", "ChemBERTa", "MolFormer", "bioinformatics", "chemoinformatics"],
  authors: [{ name: "BioLatent team" }],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${outfit.variable} ${geistMono.variable}`}>
      <body>
        {children}
      </body>
    </html>
  );
}
