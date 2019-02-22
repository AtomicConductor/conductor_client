
JOB = """

    string "title" {
        doc "Set the title that will appear in the Conductor dashboard."
        value ""
    }
    long "project" {
        doc "Set the Conductor project to render into."
        value 0
        preset "- Not set -" "0"

    }

    string "last_project" {
        value "" 
        hidden yes
    }

    attribute_group "Frames" {
        bool "use_custom_range" {
            value no
        }

        string "frame_range" {
            value "2,4-8,10-50x2"
            hidden yes
        }
        frame "chunk_size" {
            value 5
            numeric_range_min yes 1
        }
        bool "use_scout_range" {
            value no
        }
        string "scout_range" {
            value "2,4-8,10-50x2"
            hidden yes
        }

    }

    attribute_group "Image" {
        reference "source" {
            filter "Image"
        }
    }


    """
 