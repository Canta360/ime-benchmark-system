// Packs the icon PNG drawn by Capitata (icon.png) into a multi-size .ico.
// The full-size image is only padded to a square with transparency; the
// smaller sizes are high-quality reductions of it.
//
//   PackIcon.exe <icon.png> <out.ico> <out-square.png>
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;

static class PackIcon {
    static byte[] Png(Bitmap b) {
        using (var ms = new MemoryStream()) { b.Save(ms, ImageFormat.Png); return ms.ToArray(); }
    }

    static int Main(string[] args) {
        using (var src = new Bitmap(args[0])) {
            int side = Math.Max(src.Width, src.Height);
            var square = new Bitmap(side, side, PixelFormat.Format32bppArgb);
            // Copy the pixels as they are (drawing would round semi-transparent edges).
            int dx = (side - src.Width) / 2, dy = (side - src.Height) / 2;
            var from = src.LockBits(new Rectangle(0, 0, src.Width, src.Height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            var to = square.LockBits(new Rectangle(0, 0, side, side), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            var row = new byte[src.Width * 4];
            var clear = new byte[side * 4];
            for (int y = 0; y < side; y++)
                System.Runtime.InteropServices.Marshal.Copy(clear, 0, to.Scan0 + y * to.Stride, side * 4);
            for (int y = 0; y < src.Height; y++) {
                System.Runtime.InteropServices.Marshal.Copy(from.Scan0 + y * from.Stride, row, 0, row.Length);
                System.Runtime.InteropServices.Marshal.Copy(row, 0, to.Scan0 + (y + dy) * to.Stride + dx * 4, row.Length);
            }
            src.UnlockBits(from);
            square.UnlockBits(to);
            square.Save(args[2], ImageFormat.Png);
            var sizes = new List<int> { 16, 24, 32, 48, 64, 128 };
            var images = new List<byte[]>();
            foreach (int s in sizes) {
                using (var small = new Bitmap(s, s, PixelFormat.Format32bppArgb)) {
                    using (var g = Graphics.FromImage(small)) {
                        g.Clear(Color.Transparent);
                        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                        g.SmoothingMode = SmoothingMode.HighQuality;
                        g.DrawImage(square, 0, 0, s, s);
                    }
                    images.Add(Png(small));
                }
            }
            sizes.Add(side);
            images.Add(Png(square));
            using (var w = new BinaryWriter(File.Create(args[1]))) {
                w.Write((short)0); w.Write((short)1); w.Write((short)sizes.Count);
                int offset = 6 + 16 * sizes.Count;
                for (int i = 0; i < sizes.Count; i++) {
                    w.Write((byte)(sizes[i] >= 256 ? 0 : sizes[i])); w.Write((byte)(sizes[i] >= 256 ? 0 : sizes[i]));
                    w.Write((byte)0); w.Write((byte)0); w.Write((short)1); w.Write((short)32);
                    w.Write(images[i].Length); w.Write(offset);
                    offset += images[i].Length;
                }
                foreach (var b in images) w.Write(b);
            }
        }
        return 0;
    }
}
