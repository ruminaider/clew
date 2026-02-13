class Clewdex < Formula
  include Language::Python::Virtualenv

  desc "Semantic code search with hybrid retrieval and MCP integration"
  homepage "https://github.com/ruminaider/clew"
  url "https://files.pythonhosted.org/packages/source/c/clewdex/clewdex-0.1.0.tar.gz"
  sha256 "e607cd991ed9ef6ebca74848bcdc4240a9ac2b027f9f3559f1b4032b83c36342"
  license "MIT"

  depends_on "python@3.12"

  # Resource blocks for Python dependencies are auto-generated.
  # After publishing to PyPI, run:
  #   brew update-python-resources clewdex
  # to populate this section.

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      clewdex requires a running Qdrant instance and a Voyage AI API key.

      Start Qdrant:
        docker run -d -p 6333:6333 qdrant/qdrant:v1.16.1

      Set your API key:
        export VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxxxxxx

      Index your project:
        clew index /path/to/your/project --full
    EOS
  end

  test do
    assert_match "Semantic code search", shell_output("#{bin}/clew --help")
  end
end
