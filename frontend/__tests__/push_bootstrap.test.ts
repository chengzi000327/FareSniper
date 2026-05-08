import { urlBase64ToUint8Array } from "@/components/PushBootstrap";

test("urlBase64ToUint8Array decodes VAPID key into Uint8Array", () => {
  const u8 = urlBase64ToUint8Array("BNb_QvhQwq0w");
  expect(u8).toBeInstanceOf(Uint8Array);
  expect(u8.byteLength).toBe(9);
});

test("urlBase64ToUint8Array handles base64url chars + missing padding", () => {
  const u8 = urlBase64ToUint8Array("a-_b");
  expect(u8.byteLength).toBe(3);
});
