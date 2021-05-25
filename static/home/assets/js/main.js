/*
	Photon by HTML5 UP
	html5up.net | @ajlkn
	Free for personal and commercial use under the CCA 3.0 license (html5up.net/license)
*/

(function($) {

	var	$window = $(window),
		$body = $('body');

	// Breakpoints.
		breakpoints({
			xlarge:   [ '1141px',  '1680px' ],
			large:    [ '981px',   '1140px' ],
			medium:   [ '737px',   '980px'  ],
			small:    [ '481px',   '736px'  ],
			xsmall:   [ '321px',   '480px'  ],
			xxsmall:  [ null,      '320px'  ]
		});

	// Play initial animations on page load.
		$window.on('load', function() {
			window.setTimeout(function() {
				$body.removeClass('is-preload');
			}, 100);
		});

	// Scrolly.
	$('.scrolly').scrolly();

	/****************************************************************/
	// SELECTION BG COLOR
	// SELECT SOME TEXT, THEN CLICK Backspace/Delete Button FOR FUN
	/****************************************************************/
	var i = 0;
	var int = false;
	window.addEventListener('keydown', function(event) {
		var key = event.key;
		if (key === "Backspace" || key === "Delete") {
			if(int) {clearInterval(int)}
			int = setInterval(function() {
				var color = "#" + ((1<<24)*Math.random() | 0).toString(16);
				document.querySelector(':root').style.setProperty('--selection-bg', 'hsl(' + ++i + ', 70%, 50%)');
			}, 50);
		}
	});

	// IMG :)
	$('.img-hidden-custom').mouseenter(function(event) {
		var d = event.target.getAttribute("src-data");
		if(d && !event.target.getAttribute("src")) {
			event.target.setAttribute("src", d);
		}
	});

	// Open-source
	console.log("%cHey, we are open-source on GitHub. Feel free to Contribute there.", "background: #111; color: wheat; font-size: x-large");
	console.log("%chttps://github.com/ISAC-SIMO/", "font-size: large");

})(jQuery);