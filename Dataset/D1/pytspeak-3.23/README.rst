*****************************************************
pytspeak (Convert Text To Speech for Python)
*****************************************************

``pytspeak`` is a library for text-to-speech conversion in Python.

Installation
************
::

	pip install pytspeak



Usage :
************
::

    import pytspeak
    engine = pytspeak.init()
    engine.say("Hello I'm pytspeak library")
    engine.runAndWait()
	
	

::

    import pytspeak

    # Initialize the text-to-speech engine
    engine = pytspeak.init()

    # Adjusting Volume
    volume = engine.getProperty('volume')  # Get the current volume level (0.0 to 1.0)
    print("Current Volume Level:", volume)
    engine.setProperty('volume', 0.9)  # Set the volume level to 1.0 (maximum)

    # Adjusting Speaking Rate
    rate = engine.getProperty('rate')  # Get the current speaking rate
    print("Current Speaking Rate:", rate)
    engine.setProperty('rate', 120)  # Set a new speaking rate to 125 words per minute

    # Selecting Voice
    voices = engine.getProperty('voices')  # Get details of available voices
    # Change the voice to the second voice (female in this case)
    engine.setProperty('voice', voices[1].id)

    # Text-to-Speech
    engine.say("How are you ?")
    engine.say('Speaking rate is ' + str(rate))
    engine.runAndWait()

    # Saving Speech to a File
    engine.save_to_file('Good Luck', 'voice.mp3')
    engine.runAndWait()

    # Cleanup: Stop the text-to-speech engine
    engine.stop()
