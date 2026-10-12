# Turn <<Card Name>> or ((Card Name)) in a post into a Scryfall link.
#
# The migrated posts carry 2,273 card links that WordPress's tooltip plugin
# pointed at deckbox.org. Those were rewritten to Scryfall once, statically.
# This covers anything written from here on, so new posts do not reintroduce a
# dependency on a single third-party site.
#
# The URL is scryfall.com/search?q=NAME, not /card?q=NAME. /card is not a
# Scryfall endpoint and returns 404; /search redirects straight to the card page
# when the name matches exactly, and shows a useful result list when it does not.
require "cgi"

module Jekyll
  class MTGAutocard < Jekyll::Generator
    safe true

    CARD = /(?:<<(.+?)>>|\(\((.+?)\)\))/

    def generate(site)
      (site.posts.docs + site.pages).each { |doc| replace_cards(doc) }
    end

    def replace_cards(doc)
      return unless doc.content
      # Only rewrite documents that render to HTML. site.pages includes assets
      # that carry front matter, and the ((...)) pattern matches plenty of
      # ordinary JavaScript -- injecting an <a> tag mid-expression breaks it.
      return unless doc.respond_to?(:output_ext) && doc.output_ext == ".html"

      doc.content = transform(doc.content)
    end

    # Regions whose contents must never be touched. A card name does not appear
    # inside a <script>, but ordinary JavaScript is full of (( and <<.
    #
    # This is not hypothetical: the search page contains
    #     var out = esc((from ? '...' : '') + text.slice(from, to) ...)
    # and the ((...)) pattern turned that into an <a> tag mid-expression, which
    # made search.html a syntax error and broke search on the live site.
    SKIP = %r{(<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>|
               <pre\b[^>]*>.*?</pre>|<code\b[^>]*>.*?</code>)}mix

    def transform(content)
      # Split into alternating [outside, skipped, outside, skipped, ...] and only
      # rewrite the parts outside.
      content.split(SKIP).map do |part|
        part =~ /\A<(script|style|pre|code)\b/im ? part : rewrite(part)
      end.join
    end

    def rewrite(text)
      text.gsub(CARD) do
        card = (Regexp.last_match(1) || Regexp.last_match(2)).strip
        %(<a class="card-link" target="_blank" ) +
          %(href="https://scryfall.com/search?q=#{CGI.escape(card)}" ) +
          %(data-cardname="#{CGI.escape_html(card)}">#{CGI.escape_html(card)}</a>)
      end
    end
  end
end
