source "https://rubygems.org"

gem "jekyll", "~> 4.3"

group :jekyll_plugins do
  gem "jekyll-feed", "~> 0.17"
  gem "jekyll-sitemap", "~> 1.4"
  gem "jekyll-paginate", "~> 1.1"
  gem "jekyll-include-cache", "~> 0.2"
  # Old dated permalinks (/YYYY/MM/DD/slug/) 404 on the live WordPress site and
  # account for a large share of its traffic. Every migrated post declares the
  # old form in redirect_from so those links finally resolve.
  gem "jekyll-redirect-from", "~> 0.16"
end

platforms :mingw, :x64_mingw, :mswin, :jruby do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end
