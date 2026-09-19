"use client";

import { BrowserMultiFormatReader } from "@zxing/browser";
import type { IScannerControls } from "@zxing/browser";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui";

interface BarcodeScannerProps {
  onDetected: (text: string) => void;
  onClose: () => void;
}

/**
 * スマートフォン等のカメラでEAN-13バーコードを読み取るモーダル。
 * 設計仕様書 2.2節のアクティビティ図「カメラでEAN-13スキャン」に対応する。
 * getUserMedia はセキュアコンテキスト（HTTPS）でのみ動作するため、
 * ローカル開発では http://localhost からのみ、本番はデプロイ後のHTTPS URLで
 * 動作する。
 */
export function BarcodeScanner({ onDetected, onClose }: BarcodeScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  const onDetectedRef = useRef(onDetected);
  onDetectedRef.current = onDetected;

  useEffect(() => {
    const reader = new BrowserMultiFormatReader();
    let controls: IScannerControls | undefined;
    let stopped = false;
    let cancelled = false;

    reader
      .decodeFromConstraints(
        { video: { facingMode: { ideal: "environment" } } },
        videoRef.current ?? undefined,
        (result) => {
          if (result && !stopped) {
            stopped = true;
            onDetectedRef.current(result.getText());
            controls?.stop();
          }
        }
      )
      .then((c) => {
        controls = c;
        if (cancelled) {
          c.stop();
        }
      })
      .catch(() => {
        setError(
          "カメラを起動できませんでした。ブラウザにカメラの使用を許可しているか、HTTPS接続か確認してください。"
        );
      });

    return () => {
      cancelled = true;
      controls?.stop();
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 p-4">
      <div className="w-full max-w-sm overflow-hidden rounded-lg bg-black">
        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <video ref={videoRef} className="w-full" muted playsInline />
      </div>
      <p className="mt-3 text-sm text-white">バーコードを枠内に写してください</p>
      {error && <p className="mt-2 max-w-sm text-center text-sm text-red-300">{error}</p>}
      <Button type="button" variant="secondary" className="mt-4" onClick={onClose}>
        閉じる
      </Button>
    </div>
  );
}
