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

      doc.content = doc.content.gsub(CARD) do
        card = (Regexp.last_match(1) || Regexp.last_match(2)).strip
        %(<a class="card-link" target="_blank" ) +
          %(href="https://scryfall.com/search?q=#{CGI.escape(card)}" ) +
          %(data-cardname="#{CGI.escape_html(card)}">#{CGI.escape_html(card)}</a>)
      end
    end
  end
end
