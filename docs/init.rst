Initializing The Client
=======================

Authorization
-------------

Your access token may be found on your `Account page`_.

.. image:: account.png
   :alt: account page

Note the access token expires every 24 hours and will require manual refreshing. If you
have a use case that requires longer-term access to the API, please reach out to
`info@metafold3d.com <mailto:info@metafold3d.com>`_.

.. _Account page: https://app.metafold3d.com/account

Project ID
----------

At the moment all API calls must be made against a project (this may change in the
future). We recommend creating a dummy project to make API calls against. You can do
this through the app and find the project ID in the editor URL, for example::

    https://app.metafold3d.com/editor/2315

The above URL indicates the project ID is ``2315``.

Initialization
--------------

With an access token and project ID you can now initialize the
:class:`metafold.MetafoldClient` and begin making API calls! ::

    from metafold import MetafoldClient

    access_token = "..."
    project_id = "123"

    metafold = MetafoldClient(access_token, project_id)

Follow our :ref:`Quickstart guide <client-initialized>` or jump straight into some more
`complete examples`_ in the source code repo.

.. _complete examples: https://github.com/Metafold3d/metafold-python/tree/master/examples
