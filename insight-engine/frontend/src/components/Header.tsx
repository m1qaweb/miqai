import Link from 'next/link';

const Header = () => {
  return (
    <header className="bg-gray-800 text-white p-4">
      <div className="container mx-auto flex justify-between items-center">
        <h1 className="text-xl font-bold">
          <Link href="/">The Insight Engine</Link>
        </h1>
        <nav>
          <ul className="flex space-x-4">
            <li>
              <Link href="/" className="hover:text-gray-300">
                Playground 1: AI Summarization
              </Link>
            </li>
            <li>
              <Link href="/clips" className="hover:text-gray-300">
                Playground 2: Clip Extraction
              </Link>
            </li>
          </ul>
        </nav>
      </div>
    </header>
  );
};

export default Header;