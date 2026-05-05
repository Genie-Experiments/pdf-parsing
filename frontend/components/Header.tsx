import Image from "next/image";

export function Header() {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        <Image
          src="/logo-emumba.png"
          alt="Emumba"
          width={32}
          height={32}
          className="object-contain"
        />
        <span className="font-semibold text-gray-800 text-sm">Genie PDF Parser</span>
      </div>
      <Image
        src="/logo-genie-cropped.png"
        alt="Genie"
        width={28}
        height={36}
        className="object-contain"
      />
    </header>
  );
}
