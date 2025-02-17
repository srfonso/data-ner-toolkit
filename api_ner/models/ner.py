"""This module includes NER functionalities."""
import spacy
import urllib.parse

class NerAPI():
    """Ner API which uses flair models."""

    def __init__(self, spacy_model_name, disable_pipes=[]):
        self.nlp = spacy.load(spacy_model_name, disable=disable_pipes)

    def get_model(self):
        return f"{self.nlp.meta.get("lang", "<lang>")}_{self.nlp.meta.get("name", "<model>")}"
    
    def get_version(self):
        return self.nlp.meta.get("version", "<version>")

    def ner(
        self, 
        text_items: list[str], 
        allowed_types = [],
        annotate_text = False
    ):
        """Run NER to a text and return relevant entities.
        
        Parameters
        ----------
        self: self
            Reference of the instance

        text_items: list[str]
            Text list to analyze an extract their entities. Structure:
            ["text1..", "text2..", "text3.."]

        allowed_types: list, default=[] (All)
            List/tuples of entities to be taken into consideration in the result.

        annotate_text: bool, default=False
            Flag to request for text annotation.

        Returns
        ----------
        ret: list[dict]
            List of text data with the following information:
            {   
                "annotated_text": str - (Optional) Only if annotate_text is set to True
                "entities": [
                    {
                        "name": str - Entity Name
                        "type": str - Entity type
                        "start_offset": int - The first index where the entity starts in the text
                        "end_offset": int - The last index where the entity starts in the text
                    }
                    ...
                ]
            }

        """

        entities = [
            {**self._prepare_data(doc, allowed_types, annotate_text)}
            for doc in self.nlp.pipe(text_items)
        ]
        return entities

    def _prepare_data(self, doc, allowed_types = [], annotate_text = False):
        """
        Prepare the result data, if annotate_text is set to true it annotates the 
        provided text (inside the doc, doc.text) using the given entities (doc.ents).
        
        In that case it scans through the text and for each entity, replaces its 
        occurrence in the text with a formatted string using its name and type.
        If there's no entity in the text or if entities list is empty, the 
        original text is returned.
        
        Parameters
        ----------
        self : reference
            Reference to the current instance of the class.
            
        doc : spacy.tokens.doc.Doc
            The Spacy doc with the text info and its entities.
        
        allowed_types: list, default=[] (All)
            List/tuples of entities to be taken into consideration in the result.

        annotate_text: bool, default=False
            Flag to request for text annotation.

        Returns
        -------
        ret: dict
            Dict with the following structure depending if annotate_text flag was True/False
            annotate_text == True:
            {
                "entities": [
                    {
                        "name": str - Entity Name
                        "type": str - Entity type
                        "start_offset": int - The first index where the entity starts in the text
                        "end_offset": int - The last index where the entity starts in the text
                    },
                    ...
                ]
            }
            annotate_text == False
            {
                "entities": ...
                "annotated_text": "..." If no annotations are made, the original text is returned.
            }
        
        Examples
        --------
        >>> doc = nlp("Hello from New York.")
        >>> _prepare_data(doc, annotate_text=False)
        {
            "entities": [{"name": "New York", "type": "GPE", "start_offset": 11, "end_offset": 19}],
            "annotated_text": "Hello from [New York](New%20York&GPE)."
        }
        """
        annotated_text = ""
        entities = []
        last_offset = 0
        for ent in doc.ents:
            if not allowed_types or ent.label_ in allowed_types:
                ent_name = ent.text.strip()
                entities.append(
                    {
                        "name": ent_name,
                        "type": ent.label_,
                        "start_offset": ent.start_char,
                        "end_offset": ent.end_char,
                    } 
                )

                if annotate_text:
                    start, end = ent.start_char, ent.end_char
                    encoded_string = f"[{ent_name}]({urllib.parse.quote(ent_name)}&{urllib.parse.quote(ent.label_)})"
                    annotated_text += doc.text[last_offset:start] + encoded_string 
                    last_offset = end # Store the last position after the annotated entity (to avoid losing text)

        # Finally, copy the remaining text after the last entity.
        if annotate_text:
            if last_offset < len(doc.text):
                # If there are no entities this code will copy all the text into the result
                annotated_text += doc.text[last_offset:]

            return {"entities": entities, "annotated_text": annotated_text}
        
        return {"entities": entities}