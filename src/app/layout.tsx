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
  title: "BioLatent | Representation Registry & Measured Benchmark",
  description: "An open registry of chemical and biological representations with a reproducible measured benchmark for molecular, protein, and genomic tasks.",
  keywords: ["embeddings", "drug discovery", "protein language models", "molecular representations", "SMILES", "ESM-2", "ChemBERTa", "MolFormer", "bioinformatics", "chemoinformatics"],
  authors: [{ name: "Yassir Boulaamane", url: "https://github.com/yboulaamane" }],
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
